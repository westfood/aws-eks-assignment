"""Account and state isolation tests; every external command is mocked."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("environment_target", Path(__file__).with_name("target.py"))
targeting = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(targeting)
REPOSITORY = Path(__file__).resolve().parent.parent
ACCOUNTS = {"dev": "123456789012", "test": "222222222222", "prod": "333333333333"}


def configuration(environment):
    account = ACCOUNTS[environment]
    return {
        "environment": environment,
        "aws_account_id": account,
        "aws_profile": f"contoso-{environment}",
        "aws_region": "eu-central-1",
        "state_bucket_name": f"synthetic-contoso-{environment}-state",
        "infra": {
            "name": "contoso",
            "admin_cidrs": ["203.0.113.8/32"],
            "admin_principal_arn": f"arn:aws:iam::{account}:role/synthetic-deployer",
        },
    }


def outputs_for(target):
    account, environment = target.account, target.environment
    return {key: {"value": value} for key, value in {
        "environment": environment,
        "aws_account_id": account,
        "region": target.region,
        "cluster_name": target.name,
        "cluster_endpoint": f"https://{environment}.example.invalid",
        "cluster_ca": "dGVzdC1jYQ==",
        "vpc_id": "vpc-12345678",
        "public_subnet_ids": ["subnet-1", "subnet-2"],
        "public_subnet_cidrs": ["10.42.0.0/24", "10.42.1.0/24"],
        "database_subnet_cidrs": ["10.42.20.0/24", "10.42.21.0/24"],
        "database_host": "synthetic.eu-central-1.rds.amazonaws.com",
        "database_name": "contoso",
        "database_user": "contoso_app",
        "bootstrap_secret_arn": f"arn:aws:secretsmanager:eu-central-1:{account}:secret:synthetic",
        "app_role_arn": f"arn:aws:iam::{account}:role/app",
        "bootstrap_role_arn": f"arn:aws:iam::{account}:role/bootstrap",
        "controller_role_arn": f"arn:aws:iam::{account}:role/controller",
        "ecr_repository_url": f"{account}.dkr.ecr.eu-central-1.amazonaws.com/{target.name}-app",
        "admin_cidrs": ["203.0.113.8/32"],
        "waf_acl_arn": "",
        "certificate_arn": "",
        "app_hostname": "",
        "route53_zone_id": "",
        "application_url": f"https://{environment}.example.invalid",
    }.items()}


class FakeCommands:
    """A small external-boundary fake that never starts a child process."""

    def __init__(self, target):
        self.account = target.account
        self.target = target
        self.outputs = outputs_for(target)
        self.calls = []
        self.fail_bucket = False
        self.fail_plan = False
        self.fail_apply = False
        self.fail_scan = False
        self.kube_document = {
            "contexts": [{"name": target.name, "context": {"cluster": "selected-cluster", "user": "selected-user"}}],
            "clusters": [{"name": "selected-cluster", "cluster": {
                "server": self.outputs["cluster_endpoint"]["value"],
                "certificate-authority-data": self.outputs["cluster_ca"]["value"],
            }}],
        }

    def __call__(self, command, capture=False, stage=None):
        self.calls.append((list(command), capture, stage))
        if command[0] == "aws":
            if "get-caller-identity" in command:
                return json.dumps({"Account": self.account})
            if "head-bucket" in command:
                if self.fail_bucket:
                    raise subprocess.CalledProcessError(403, command)
                return ""
            if "get-login-password" in command:
                print("synthetic-login-token")
                return None
            if "get-registry-scanning-configuration" in command:
                return json.dumps({"registryId": self.account,
                                   "scanningConfiguration": {"scanType": self.target.infra.get("ecr_scan_type", "BASIC")}})
            if "batch-get-repository-scanning-configuration" in command:
                repository = self.outputs["ecr_repository_url"]["value"].split("/", 1)[1]
                return json.dumps({"scanningConfigurations": [{
                    "repositoryName": repository,
                    "repositoryArn": f"arn:aws:ecr:{self.target.region}:{self.account}:repository/{repository}",
                    "scanFrequency": "CONTINUOUS_SCAN" if self.target.infra.get("ecr_scan_type") == "ENHANCED" else "SCAN_ON_PUSH",
                }]})
            if "describe-image-scan-findings" in command:
                request = json.loads(command[command.index("--cli-input-json") + 1])
                enhanced = self.target.infra.get("ecr_scan_type") == "ENHANCED"
                return json.dumps({"registryId": self.account, "repositoryName": request["repositoryName"],
                    "imageId": request["imageId"], "imageScanStatus": {"status": "ACTIVE" if enhanced else "COMPLETE"},
                    "imageScanFindings": {
                        "imageScanCompletedAt": datetime.now(timezone.utc).isoformat(),
                        "findingSeverityCounts": {"HIGH": 1} if self.fail_scan else {},
                        "enhancedFindings" if enhanced else "findings": [],
                    }})
        if command[0] == "terraform":
            if "plan" in command:
                if self.fail_plan:
                    raise subprocess.CalledProcessError(1, command)
                output = next(arg.split("=", 1)[1] for arg in command if arg.startswith("-out="))
                Path(output).write_bytes(b"synthetic saved plan; not a real Terraform plan")
                return None
            if "apply" in command:
                if self.fail_apply:
                    raise subprocess.CalledProcessError(1, command)
                return None
            if "output" in command:
                return json.dumps(self.outputs)
            if "init" in command:
                return None
        if command[0] == "kubectl" and "view" in command:
            return json.dumps(self.kube_document)
        if command[0] == "kubectl":
            return None
        raise AssertionError(f"Unmocked external command: {command[0]}")


class EnvironmentTargetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aws-target-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "environments").mkdir()
        for environment in targeting.ENVIRONMENTS:
            self.save_config(environment, configuration(environment))
        for stage in targeting.STAGES:
            directory = self.root / stage
            directory.mkdir()
            (directory / "main.tf").write_text('# Synthetic source, never executed.\n')
            (directory / ".terraform.lock.hcl").write_text('# Synthetic provider lock.\n')
        # Any accidentally unmocked subprocess would fail rather than reach AWS.
        process_guard = patch.object(targeting.subprocess, "run", side_effect=AssertionError("External process forbidden in target tests"))
        process_guard.start()
        self.addCleanup(process_guard.stop)
        self.output = io.StringIO()
        stdout = redirect_stdout(self.output)
        stderr = redirect_stderr(self.output)
        stdout.__enter__()
        stderr.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)
        self.addCleanup(stderr.__exit__, None, None, None)

    def save_config(self, environment, value):
        path = self.root / "environments" / f"{environment}.json"
        path.write_text(json.dumps(value))
        return path

    def target(self, environment="dev"):
        return targeting.Target(environment, root=self.root)

    def write_outputs(self, target, stage="infra", values=None):
        path = target.directory / f"{stage}-outputs.json"
        targeting.write_private(path, values or outputs_for(target))
        return path

    def plan(self, target, *, stage="infra", destroy=False, ingress_only=False):
        fake = FakeCommands(target)
        with patch.object(target, "run", side_effect=fake):
            target.terraform(stage, "plan", destroy=destroy, ingress_only=ingress_only)
        suffix = ("-ingress" if ingress_only else "") + ("-destroy" if destroy else "")
        plan = target.directory / "plans" / f"{stage}{suffix}.tfplan"
        return plan, plan.with_suffix(".json"), fake

    def test_each_environment_has_separate_state_cache_inputs_and_kubeconfig(self):
        state_paths, data_paths, bucket_names, keys, kubeconfigs = set(), set(), set(), set(), set()
        for environment in targeting.ENVIRONMENTS:
            selected = self.target(environment)
            bootstrap_inputs, bootstrap_backend = selected.prepare("bootstrap")
            state_paths.add(json.loads(bootstrap_backend.read_text().splitlines()[0].split(" = ", 1)[1]))
            infra_inputs, infra_backend = selected.prepare("infra")
            backend = {line.split(" = ", 1)[0]: json.loads(line.split(" = ", 1)[1]) for line in infra_backend.read_text().splitlines()}
            values = json.loads(infra_inputs.read_text())
            self.assertEqual(values["environment"], environment)
            self.assertEqual(values["aws_account_id"], ACCOUNTS[environment])
            self.assertEqual(backend["allowed_account_ids"], [ACCOUNTS[environment]])
            self.assertTrue(backend["encrypt"] and backend["use_lockfile"])
            self.assertIn(f"/{environment}/", backend["key"])
            bucket_names.add(backend["bucket"])
            keys.add(backend["key"])
            kubeconfigs.add(selected.kubeconfig)
            for stage in targeting.STAGES:
                data_paths.add(selected.child_env(stage)["TF_DATA_DIR"])
            for private in (bootstrap_inputs, bootstrap_backend, infra_inputs, infra_backend):
                self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
                self.assertIn(environment, private.parts)
        self.assertEqual(len(state_paths), 3)
        self.assertEqual(len(bucket_names), 3)
        self.assertEqual(len(keys), 3)
        self.assertEqual(len(kubeconfigs), 3)
        self.assertEqual(len(data_paths), 9)

    def test_ambient_credentials_inputs_and_workspaces_cannot_change_target(self):
        selected = self.target()
        ambient = {name: "synthetic-unwanted-value" for name in targeting.CREDENTIAL_VARIABLES}
        ambient.update(AWS_PROFILE="prod", AWS_DEFAULT_PROFILE="prod", AWS_REGION="us-east-1",
                       AWS_ENDPOINT_URL="https://other.example.invalid", AWS_ENDPOINT_URL_STS="https://other.example.invalid",
                       TF_VAR_environment="prod", TF_VAR_aws_account_id=ACCOUNTS["prod"],
                       TF_CLI_ARGS="-input=false", TF_CLI_ARGS_plan="-destroy", TF_WORKSPACE="prod",
                       TF_DATA_DIR="/unrelated/cache", KUBECONFIG="/unrelated/kubeconfig")
        with patch.dict(os.environ, ambient):
            child = selected.child_env("infra")
            for name in (*targeting.CREDENTIAL_VARIABLES, "AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_STS", "TF_VAR_environment", "TF_VAR_aws_account_id", "TF_CLI_ARGS", "TF_CLI_ARGS_plan"):
                self.assertNotIn(name, child)
            self.assertEqual(child["AWS_PROFILE"], "contoso-dev")
            self.assertEqual(child["AWS_REGION"], "eu-central-1")
            self.assertEqual(child["TF_WORKSPACE"], "default")
            self.assertEqual(child["TF_DATA_DIR"], str(selected.directory / "terraform" / "infra"))
            self.assertEqual(child["KUBECONFIG"], str(selected.kubeconfig))
            self.assertEqual(os.environ["AWS_PROFILE"], "prod", "The parent shell must remain untouched")

    def test_account_profile_and_bucket_must_be_distinct_between_environments(self):
        for field in ("aws_account_id", "aws_profile", "state_bucket_name"):
            with self.subTest(field=field):
                value = configuration("test")
                value[field] = configuration("dev")[field]
                if field == "aws_account_id":
                    value["infra"]["admin_principal_arn"] = configuration("dev")["infra"]["admin_principal_arn"]
                self.save_config("test", value)
                with self.assertRaisesRegex(ValueError, "must be different"):
                    self.target("test")
                self.save_config("test", configuration("test"))

    def test_swapped_config_or_foreign_administrator_is_rejected(self):
        value = configuration("dev")
        value["environment"] = "prod"
        self.save_config("dev", value)
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.target()
        value = configuration("dev")
        value["infra"]["admin_principal_arn"] = configuration("prod")["infra"]["admin_principal_arn"]
        self.save_config("dev", value)
        with self.assertRaisesRegex(ValueError, "selected account"):
            self.target()

    def test_public_examples_require_real_private_account_configuration(self):
        for environment in targeting.ENVIRONMENTS:
            with self.subTest(environment=environment):
                with self.assertRaisesRegex(ValueError, "12-digit"):
                    targeting.Target(environment, root=self.root, config_path=REPOSITORY / "environments" / f"{environment}.example.json")

    def test_existing_auto_loaded_tfvars_cannot_leak_into_target(self):
        selected = self.target()
        for name in ("terraform.tfvars", "terraform.tfvars.json", "legacy.auto.tfvars", "legacy.auto.tfvars.json"):
            with self.subTest(name=name):
                path = self.root / "infra" / name
                path.write_text('environment = "prod"')
                with self.assertRaisesRegex(ValueError, "auto-loaded"):
                    selected.prepare("infra")
                path.unlink()

    def test_wrong_sts_account_stops_before_backend_or_terraform(self):
        selected = self.target()
        fake = FakeCommands(selected)
        fake.account = ACCOUNTS["prod"]
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaisesRegex(ValueError, "Credential account mismatch"):
                selected.terraform("infra", "init")
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("get-caller-identity", fake.calls[0][0])

    def test_state_bucket_owner_failure_stops_before_terraform(self):
        selected = self.target()
        fake = FakeCommands(selected)
        fake.fail_bucket = True
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaises(subprocess.CalledProcessError):
                selected.terraform("infra", "init")
        self.assertFalse(any(command[0] == "terraform" for command, _, _ in fake.calls))
        bucket = next(command for command, _, _ in fake.calls if "head-bucket" in command)
        self.assertEqual(bucket[bucket.index("--expected-bucket-owner") + 1], selected.account)

    def test_aws_identity_endpoint_and_unsigned_overrides_are_rejected(self):
        selected = self.target()
        for flag in ("--profile", "--prof", "--region=us-east-1", "--reg", "--endpoint-u", "--no-verify-ssl", "--no-sign-request"):
            with self.subTest(flag=flag), patch.object(selected, "run") as run:
                with self.assertRaisesRegex(ValueError, "overrides"):
                    selected.aws(["sts", "get-caller-identity", flag, "synthetic"])
                run.assert_not_called()

    def test_kubectl_destination_and_tls_overrides_are_rejected(self):
        selected = self.target()
        for flag in ("--context", "--kubeconfig=other", "--server", "-shttps://other.invalid", "--token", "--insecure-skip-tls-verify=true"):
            with self.subTest(flag=flag), patch.object(selected, "run") as run:
                with self.assertRaisesRegex(ValueError, "overrides"):
                    selected.kubectl(["get", "pods", flag])
                run.assert_not_called()

    def test_aws_guard_output_does_not_corrupt_login_password_stdout(self):
        selected = self.target()
        fake = FakeCommands(selected)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(selected, "run", side_effect=fake), redirect_stdout(stdout), redirect_stderr(stderr):
            selected.aws(["ecr", "get-login-password"])
        self.assertEqual(stdout.getvalue(), "synthetic-login-token\n")
        self.assertIn("Target verified: dev", stderr.getvalue())

    def test_mixed_environment_or_account_outputs_are_rejected(self):
        selected = self.target()
        for field, wrong in (("environment", "prod"), ("aws_account_id", ACCOUNTS["prod"])):
            with self.subTest(field=field):
                values = outputs_for(selected)
                values[field]["value"] = wrong
                self.write_outputs(selected, values=values)
                with self.assertRaisesRegex(ValueError, "different environment/account"):
                    selected.load_outputs("infra")
        values = outputs_for(selected)
        values["cluster_name"]["value"] = "unrelated-dev"
        self.write_outputs(selected, values=values)
        with self.assertRaisesRegex(ValueError, "different target cluster"):
            selected.load_outputs("infra")

    def test_platform_inputs_reject_foreign_ecr_then_write_selected_metadata(self):
        selected = self.target()
        values = outputs_for(selected)
        self.write_outputs(selected, values=values)
        image = values["ecr_repository_url"]["value"] + "@sha256:" + "a" * 64
        with self.assertRaisesRegex(ValueError, "this target account"):
            selected.platform_inputs(image.replace(selected.account, ACCOUNTS["prod"]))
        fake = FakeCommands(selected)
        with patch.object(selected, "run", side_effect=fake):
            selected.platform_inputs(image)
        path = selected.directory / "inputs" / "platform.tfvars.json"
        inputs = json.loads(path.read_text())
        self.assertEqual(inputs["environment"], "dev")
        self.assertEqual(inputs["aws_account_id"], selected.account)
        self.assertEqual(inputs["app_image"], image)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaisesRegex(ValueError, "Refusing to replace"):
                selected.platform_inputs(image)

    def platform_fixture(self):
        selected = self.target()
        self.write_outputs(selected)
        image = outputs_for(selected)["ecr_repository_url"]["value"] + "@sha256:" + "a" * 64
        fake = FakeCommands(selected)
        with patch.object(selected, "run", side_effect=fake):
            selected.platform_inputs(image)
        fake.calls.clear()
        return selected, image, fake

    def test_image_gate_failure_prevents_platform_input_creation(self):
        selected = self.target()
        self.write_outputs(selected)
        image = outputs_for(selected)["ecr_repository_url"]["value"] + "@sha256:" + "a" * 64
        fake = FakeCommands(selected)
        fake.fail_scan = True
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaisesRegex(ValueError, "1 HIGH"):
                selected.platform_inputs(image)
        self.assertFalse((selected.directory / "inputs" / "platform.tfvars.json").exists())

    def test_platform_plan_rechecks_security_before_any_terraform_plan(self):
        selected, _, fake = self.platform_fixture()
        fake.fail_scan = True
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaisesRegex(ValueError, "1 HIGH"):
                selected.terraform("platform", "plan")
        self.assertFalse(any(command[0] == "terraform" for command, _, _ in fake.calls))
        self.assertFalse((selected.directory / "plans" / "platform.json").exists())

    def test_platform_apply_rechecks_findings_after_successful_plan(self):
        selected, _, fake = self.platform_fixture()
        with patch.object(selected, "run", side_effect=fake):
            selected.terraform("platform", "plan")
            fake.fail_scan = True
            with self.assertRaisesRegex(ValueError, "1 HIGH"):
                selected.terraform("platform", "apply")
        scans = [command for command, _, _ in fake.calls if "describe-image-scan-findings" in command]
        self.assertEqual(len(scans), 2, "Apply must re-read ECR; plan evidence cannot authorize a later release")
        self.assertFalse(any(command[0] == "terraform" and "apply" in command for command, _, _ in fake.calls))

    def test_destroy_remains_possible_when_image_is_vulnerable_or_unavailable(self):
        selected, _, fake = self.platform_fixture()
        for ingress_only in (False, True):
            fake.calls.clear()
            fake.fail_scan = True
            with self.subTest(ingress_only=ingress_only), patch.object(selected, "run", side_effect=fake), \
                    patch.object(selected, "scan_image", side_effect=AssertionError("Teardown must not depend on ECR")) as scanner:
                selected.terraform("platform", "plan", destroy=True, ingress_only=ingress_only)
                selected.terraform("platform", "apply", destroy=True, ingress_only=ingress_only)
                scanner.assert_not_called()
            self.assertTrue(any(command[0] == "terraform" and "apply" in command for command, _, _ in fake.calls))

    def test_scan_command_checks_account_before_reading_ecr(self):
        selected, image, fake = self.platform_fixture()
        fake.account = ACCOUNTS["prod"]
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaisesRegex(ValueError, "Credential account mismatch"):
                selected.scan_image(image)
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("get-caller-identity", fake.calls[0][0])

    def test_cli_scan_image_forwards_explicit_digest_and_wait(self):
        with patch.object(targeting, "Target") as constructor:
            image = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/contoso-dev-app@sha256:" + "a" * 64
            self.assertEqual(targeting.main(["--env", "dev", "scan-image", "--image", image, "--wait-seconds", "0"]), 0)
            constructor.return_value.scan_image.assert_called_once_with(image, 0)

    def test_mixed_platform_inputs_are_rejected_before_backend_access(self):
        selected = self.target()
        targeting.write_private(selected.directory / "inputs" / "platform.tfvars.json", {
            "environment": "prod", "aws_account_id": ACCOUNTS["prod"], "aws_region": "eu-central-1",
        })
        with self.assertRaisesRegex(ValueError, "another environment/account/Region"):
            selected.terraform("platform", "init")

    def test_wrong_kubeconfig_server_or_ca_prevents_cluster_api_command(self):
        selected = self.target()
        self.write_outputs(selected)
        selected.kubeconfig.write_text("synthetic; mocked kubectl supplies parsed JSON")
        for field in ("server", "certificate-authority-data"):
            with self.subTest(field=field):
                fake = FakeCommands(selected)
                fake.kube_document["clusters"][0]["cluster"][field] = "foreign"
                with patch.object(selected, "run", side_effect=fake):
                    with self.assertRaisesRegex(ValueError, "endpoint/CA"):
                        selected.kubectl(["get", "pods"])
                kubectl_calls = [command for command, _, _ in fake.calls if command[0] == "kubectl"]
                self.assertEqual(len(kubectl_calls), 1)
                self.assertIn("view", kubectl_calls[0])

    def test_valid_kubectl_always_uses_only_selected_private_context(self):
        selected = self.target("test")
        self.write_outputs(selected)
        selected.kubeconfig.write_text("synthetic kubeconfig")
        fake = FakeCommands(selected)
        with patch.object(selected, "run", side_effect=fake):
            selected.kubectl(["get", "pods", "-n", "contoso"])
        command = fake.calls[-1][0]
        self.assertEqual(command[:5], ["kubectl", "--kubeconfig", str(selected.kubeconfig), "--context", "contoso-test"])
        self.assertEqual(command[5:], ["get", "pods", "-n", "contoso"])

    def test_demo_rejects_test_and_prod_before_config_or_api_access(self):
        for environment in ("test", "prod"):
            with self.subTest(environment=environment), patch.object(targeting, "Target") as constructor:
                with self.assertRaises(SystemExit) as raised:
                    targeting.main(["--env", environment, "demo"])
                self.assertEqual(raised.exception.code, 1)
                constructor.assert_not_called()
        for environment in ("test", "prod"):
            with self.subTest(direct=environment):
                with self.assertRaisesRegex(ValueError, "restricted to dev"):
                    self.target(environment).demo()

    def test_cli_needs_explicit_known_environment(self):
        for arguments in (["show"], ["--env", "qa", "show"]):
            with self.subTest(arguments=arguments):
                with self.assertRaises(SystemExit) as raised:
                    targeting.main(arguments)
                self.assertEqual(raised.exception.code, 2)

    def test_cli_forwards_leading_namespace_help_and_query_arguments(self):
        cases = (
            ("kubectl", ["-n", "contoso", "get", "pods"]),
            ("kubectl", ["--help"]),
            ("aws", ["--query", "Account", "sts", "get-caller-identity", "--output", "text"]),
            ("aws", ["s3api", "head-bucket", "--bucket", "synthetic-bucket", "--help"]),
        )
        for command, arguments in cases:
            with self.subTest(command=command, arguments=arguments), patch.object(targeting, "Target") as constructor:
                self.assertEqual(targeting.main(["--env", "dev", command, *arguments]), 0)
                constructor.assert_called_once_with("dev", config_path=None)
                getattr(constructor.return_value, command).assert_called_once_with(arguments)

    def test_cli_rejects_unrecognized_flags_for_non_passthrough_commands(self):
        with patch.object(targeting, "Target") as constructor:
            with self.assertRaises(SystemExit) as raised:
                targeting.main(["--env", "dev", "show", "--unexpected"])
            self.assertEqual(raised.exception.code, 2)
            constructor.assert_not_called()

    def test_process_boundary_receives_selected_environment_and_private_umask(self):
        selected = self.target("prod")
        process = subprocess.CompletedProcess(["terraform"], 0, "synthetic stdout", "")
        with patch.object(targeting.subprocess, "run", return_value=process) as run:
            result = selected.run(["terraform", "version"], capture=True, stage="infra")
        self.assertEqual(result, "synthetic stdout")
        arguments = run.call_args.kwargs
        self.assertEqual(arguments["cwd"], self.root.resolve())
        self.assertEqual(arguments["env"]["AWS_PROFILE"], "contoso-prod")
        self.assertEqual(arguments["env"]["TF_DATA_DIR"], str(selected.directory / "terraform" / "infra"))
        self.assertEqual(arguments["umask"], 0o077)
        self.assertTrue(arguments["check"])

    def test_plan_then_apply_preserves_account_guard_and_consumes_manifest(self):
        selected = self.target()
        plan, manifest, _ = self.plan(selected)
        self.assertEqual(stat.S_IMODE(plan.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), 0o600)
        fake = FakeCommands(selected)
        with patch.object(selected, "run", side_effect=fake):
            selected.terraform("infra", "apply")
        self.assertFalse(manifest.exists())
        command, _, stage = fake.calls[-1]
        self.assertEqual(command, ["terraform", "-chdir=infra", "apply", "-input=false", str(plan)])
        self.assertEqual(stage, "infra")
        with self.assertRaisesRegex(ValueError, "Create and review"):
            selected.terraform("infra", "apply")

    def test_tampered_plan_or_changed_source_cannot_be_applied(self):
        for change in ("plan", "source", "policy"):
            with self.subTest(change=change):
                selected = self.target()
                policy = self.root / "infra" / "policies" / "policy.json"
                policy.parent.mkdir(exist_ok=True)
                policy.write_text('{"Statement": []}')
                plan, _, _ = self.plan(selected)
                if change == "plan":
                    plan.write_bytes(plan.read_bytes() + b"changed")
                elif change == "source":
                    (self.root / "infra" / "main.tf").write_text('# Changed desired infrastructure\n')
                else:
                    policy.write_text('{"Statement": [{"Effect": "Deny"}]}')
                with self.assertRaisesRegex(ValueError, "stale or belongs"):
                    selected.terraform("infra", "apply")

    def test_saved_plan_cannot_cross_accounts_or_operation_types(self):
        selected = self.target()
        plan, manifest, _ = self.plan(selected)
        other = self.target("prod")
        other.prepare("infra")
        other_plan = other.directory / "plans" / plan.name
        other_plan.parent.mkdir()
        shutil.copy2(plan, other_plan)
        shutil.copy2(manifest, other_plan.with_suffix(".json"))
        with self.assertRaisesRegex(ValueError, "stale or belongs"):
            other.terraform("infra", "apply")
        destroy_plan = plan.with_name("infra-destroy.tfplan")
        shutil.copy2(plan, destroy_plan)
        shutil.copy2(manifest, destroy_plan.with_suffix(".json"))
        with self.assertRaisesRegex(ValueError, "stale or belongs"):
            selected.terraform("infra", "apply", destroy=True)

    def test_changed_profile_requires_a_new_reviewed_plan(self):
        selected = self.target()
        self.plan(selected)
        updated = configuration("dev")
        updated["aws_profile"] = "contoso-dev-new-session-profile"
        self.save_config("dev", updated)
        with self.assertRaisesRegex(ValueError, "stale or belongs"):
            self.target().terraform("infra", "apply")

    def test_failed_replan_and_failed_apply_invalidate_old_plan_manifest(self):
        selected = self.target()
        _, manifest, _ = self.plan(selected)
        fake = FakeCommands(selected)
        fake.fail_plan = True
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaises(subprocess.CalledProcessError):
                selected.terraform("infra", "plan")
        self.assertFalse(manifest.exists())
        _, manifest, _ = self.plan(selected)
        fake.fail_plan, fake.fail_apply = False, True
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaises(subprocess.CalledProcessError):
                selected.terraform("infra", "apply")
        self.assertFalse(manifest.exists())

    def test_mismatched_output_snapshot_is_never_saved(self):
        selected = self.target()
        fake = FakeCommands(selected)
        fake.outputs["environment"]["value"] = "prod"
        with patch.object(selected, "run", side_effect=fake):
            with self.assertRaisesRegex(ValueError, "different environment/account"):
                selected.terraform("infra", "output")
        self.assertFalse((selected.directory / "infra-outputs.json").exists())

    def test_ingress_only_requires_platform_destroy(self):
        selected = self.target()
        for stage, destroy in (("infra", True), ("platform", False)):
            with self.subTest(stage=stage, destroy=destroy):
                with self.assertRaisesRegex(ValueError, "only valid for platform"):
                    selected.terraform(stage, "plan", destroy=destroy, ingress_only=True)


if __name__ == "__main__":
    unittest.main()
