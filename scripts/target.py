#!/usr/bin/env python3
"""Run a command against one explicit AWS account and isolated environment state."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENTS = ("dev", "test", "prod")
STAGES = ("bootstrap", "infra", "platform")
CREDENTIAL_VARIABLES = {
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN",
    "AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_SESSION_NAME",
    "AWS_CONTAINER_CREDENTIALS_FULL_URI", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "AWS_CONTAINER_AUTHORIZATION_TOKEN", "AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE",
}


def write_private(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".target-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_helper(filename, name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Target:
    def __init__(self, environment, root=ROOT, config_path=None):
        if environment not in ENVIRONMENTS:
            raise ValueError("Select dev, test or prod explicitly")
        self.environment = environment
        self.root = Path(root).resolve()
        self.config_path = Path(config_path) if config_path else self.root / "environments" / f"{environment}.json"
        if not self.config_path.is_file():
            raise ValueError(f"Configure environments/{environment}.json from its .example.json first")
        self.config = json.loads(self.config_path.read_text())
        required = {"environment", "aws_account_id", "aws_profile", "aws_region", "state_bucket_name", "infra"}
        if not isinstance(self.config, dict) or set(self.config) != required:
            raise ValueError("Environment config must contain exactly: " + ", ".join(sorted(required)))
        if self.config["environment"] != environment:
            raise ValueError("Config environment does not match --env")
        self.account = self.config["aws_account_id"]
        if not isinstance(self.account, str) or not re.fullmatch(r"\d{12}", self.account):
            raise ValueError("Replace aws_account_id with the selected account's 12-digit ID")
        self.profile, self.region = self.config["aws_profile"], self.config["aws_region"]
        if not isinstance(self.profile, str) or not self.profile.strip() or any(c in self.profile for c in "\r\n"):
            raise ValueError("Set a named AWS profile for this environment")
        if not isinstance(self.region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", self.region):
            raise ValueError("Set a commercial AWS Region such as eu-central-1")
        self.bucket = self.config["state_bucket_name"]
        if not isinstance(self.bucket, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket) or "replace" in self.bucket.lower():
            raise ValueError("Set a globally unique state_bucket_name owned by this account")
        self.infra = self.config["infra"]
        if not isinstance(self.infra, dict) or {"environment", "aws_account_id", "aws_region"} & self.infra.keys():
            raise ValueError("infra must be an object; environment/account/Region come from the target")
        self.name = f"{self.infra.get('name', 'contoso')}-{environment}"
        admin = self.infra.get("admin_principal_arn", "")
        if not re.fullmatch(rf"arn:aws:iam::{self.account}:(?:role|user)/.+", admin):
            raise ValueError("infra.admin_principal_arn must be an IAM user/role in the selected account")
        for other in ENVIRONMENTS:
            path = self.root / "environments" / f"{other}.json"
            if other != environment and path.is_file():
                other_config = json.loads(path.read_text())
                for field in ("aws_account_id", "aws_profile", "state_bucket_name"):
                    if other_config.get(field) == self.config[field]:
                        raise ValueError(f"{field} must be different for {environment} and {other}")
        self.directory = self.root / ".local" / environment
        self.kubeconfig = self.directory / "kubeconfig"

    def child_env(self, stage=None):
        values = dict(os.environ)
        for key in list(values):
            if key in CREDENTIAL_VARIABLES or key.startswith(("TF_VAR_", "TF_CLI_ARGS", "AWS_ENDPOINT_URL")):
                values.pop(key)
        values.update(AWS_PROFILE=self.profile, AWS_DEFAULT_PROFILE=self.profile,
                      AWS_REGION=self.region, AWS_DEFAULT_REGION=self.region,
                      AWS_EC2_METADATA_DISABLED="true", AWS_PAGER="", TF_WORKSPACE="default",
                      KUBECONFIG=str(self.kubeconfig))
        values.pop("TF_DATA_DIR", None)
        if stage:
            values["TF_DATA_DIR"] = str(self.directory / "terraform" / stage)
        return values

    def run(self, command, capture=False, stage=None):
        result = subprocess.run(command, cwd=self.root, env=self.child_env(stage),
                                text=True, capture_output=capture, check=True, umask=0o077)
        return result.stdout if capture else None

    def aws_command(self, *arguments):
        return ["aws", "--profile", self.profile, "--region", self.region, *arguments]

    def check_account(self):
        identity = json.loads(self.run(self.aws_command("sts", "get-caller-identity", "--output", "json"), capture=True))
        if identity.get("Account") != self.account:
            raise ValueError(f"Credential account mismatch for {self.environment}; no target command was run")
        print(f"Target verified: {self.environment} / account {self.account} / profile {self.profile}", file=sys.stderr)

    def check_bucket(self):
        self.run(self.aws_command("s3api", "head-bucket", "--bucket", self.bucket,
                                  "--expected-bucket-owner", self.account), capture=True)

    def load_outputs(self, stage):
        path = self.directory / f"{stage}-outputs.json"
        if not path.is_file():
            raise ValueError(f"Run target terraform {stage} output for {self.environment} first")
        outputs = json.loads(path.read_text())
        self.validate_outputs(outputs)
        if stage == "infra" and outputs.get("cluster_name", {}).get("value") != self.name:
            raise ValueError("Infrastructure outputs name a different target cluster")
        return outputs

    def validate_outputs(self, outputs):
        if outputs.get("environment", {}).get("value") != self.environment or outputs.get("aws_account_id", {}).get("value") != self.account:
            raise ValueError("Output metadata belongs to a different environment/account")

    def prepare(self, stage):
        source = self.root / stage
        auto = [source / "terraform.tfvars", source / "terraform.tfvars.json", *source.glob("*.auto.tfvars"), *source.glob("*.auto.tfvars.json")]
        if any(p.exists() for p in auto):
            raise ValueError(f"Move auto-loaded input files out of {stage}/ into the selected environments/<env>.json")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        common = {"environment": self.environment, "aws_account_id": self.account, "aws_region": self.region}
        inputs = self.directory / "inputs" / f"{stage}.tfvars.json"
        if stage == "bootstrap":
            write_private(inputs, {**common, "state_bucket_name": self.bucket})
            backend = {"path": str(self.directory / "bootstrap" / "terraform.tfstate"),
                       "workspace_dir": str(self.directory / "bootstrap" / "workspaces")}
            (self.directory / "bootstrap").mkdir(mode=0o700, exist_ok=True)
        else:
            backend = {"bucket": self.bucket, "key": f"contoso/{self.environment}/{stage}/terraform.tfstate",
                       "region": self.region, "profile": self.profile, "encrypt": True,
                       "use_lockfile": True, "allowed_account_ids": [self.account]}
            if stage == "infra":
                write_private(inputs, {**self.infra, **common})
            else:
                if not inputs.is_file():
                    raise ValueError("Generate selected platform-inputs with an immutable image first")
                selected = json.loads(inputs.read_text())
                if any(selected.get(k) != v for k, v in common.items()):
                    raise ValueError("Platform inputs belong to another environment/account/Region")
        backend_path = self.directory / "backends" / f"{stage}.hcl"
        # JSON values are valid HCL expressions; credentials are never serialized.
        backend_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(backend_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write("\n".join(f"{k} = {json.dumps(v)}" for k, v in backend.items()) + "\n")
        (self.directory / "terraform" / stage).mkdir(parents=True, exist_ok=True, mode=0o700)
        return inputs, backend_path

    def fingerprint(self, stage, inputs, backend):
        digest = hashlib.sha256(json.dumps(self.config, sort_keys=True).encode())
        paths = sorted(p for p in (self.root / stage).rglob("*")
                       if p.is_file() and p.suffix in (".tf", ".json")
                       and ".terraform" not in p.parts and "tests" not in p.parts)
        paths += [self.root / stage / ".terraform.lock.hcl", inputs, backend]
        for path in paths:
            if path.is_file():
                digest.update(str(path.relative_to(self.root)).encode())
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def terraform(self, stage, action, destroy=False, ingress_only=False):
        if ingress_only and (stage != "platform" or not destroy):
            raise ValueError("--ingress-only is only valid for platform --destroy plans/applies")
        if (destroy or ingress_only) and action not in ("plan", "apply"):
            raise ValueError("Destroy flags apply only to plan/apply")
        inputs, backend = self.prepare(stage)
        suffix = ("-ingress" if ingress_only else "") + ("-destroy" if destroy else "")
        plan = self.directory / "plans" / f"{stage}{suffix}.tfplan"
        manifest = plan.with_suffix(".json")
        fingerprint = self.fingerprint(stage, inputs, backend)
        expected = {"environment": self.environment, "aws_account_id": self.account,
                    "stage": stage, "destroy": destroy, "ingress_only": ingress_only,
                    "configuration_sha256": fingerprint}
        if action == "plan":
            manifest.unlink(missing_ok=True)
        if action == "apply":
            if not plan.is_file() or not manifest.is_file():
                raise ValueError("Create and review a plan for this target and operation first")
            recorded = json.loads(manifest.read_text())
            if any(recorded.get(k) != v for k, v in expected.items()) or recorded.get("plan_sha256") != hashlib.sha256(plan.read_bytes()).hexdigest():
                raise ValueError("Saved plan is stale or belongs to a different target/operation; create a new plan")
        self.check_account()
        if stage != "bootstrap":
            self.check_bucket()
        # Re-read ECR at release time: a clean report from input generation can
        # become outdated before plan/apply. Teardown must remain possible even
        # when an image is vulnerable, unscannable, or has been deleted.
        if stage == "platform" and action in ("plan", "apply") and not destroy:
            image = json.loads(inputs.read_text()).get("app_image")
            self.scan_image(image, account_checked=True)
        command = ["terraform", f"-chdir={stage}"]
        if action == "init":
            self.run(command + ["init", "-input=false", "-reconfigure", "-lockfile=readonly", f"-backend-config={backend}"], stage=stage)
        elif action == "plan":
            plan.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            args = command + ["plan", "-input=false", f"-var-file={inputs}", f"-out={plan}"]
            if destroy:
                args.append("-destroy")
            if ingress_only:
                args.append("-target=kubernetes_ingress_v1.app")
            self.run(args, stage=stage)
            os.chmod(plan, 0o600)
            write_private(manifest, {**expected, "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest()})
            print(f"Reviewed-plan candidate: {plan}", file=sys.stderr)
        elif action == "apply":
            manifest.unlink()
            self.run(command + ["apply", "-input=false", str(plan)], stage=stage)
        elif action == "output":
            outputs = json.loads(self.run(command + ["output", "-json"], capture=True, stage=stage))
            self.validate_outputs(outputs)
            path = self.directory / f"{stage}-outputs.json"
            write_private(path, outputs)
            print(f"Wrote {path}", file=sys.stderr)

    @staticmethod
    def reject_overrides(arguments, flags):
        if any(arg.split("=", 1)[0] in flags or
               (arg.startswith("--") and any(flag.startswith(arg.split("=", 1)[0]) for flag in flags)) or
               ("-s" in flags and arg.startswith("-s") and not arg.startswith("--"))
               for arg in arguments):
            raise ValueError("Target identity, endpoint and context overrides are not accepted")

    def aws(self, arguments):
        self.reject_overrides(arguments, {"--profile", "--region", "--endpoint-url", "--no-verify-ssl", "--no-sign-request"})
        self.check_account()
        self.run(self.aws_command(*arguments))

    def create_kubeconfig(self):
        outputs = self.load_outputs("infra")
        self.check_account()
        self.run(self.aws_command("eks", "update-kubeconfig", "--name", self.name,
                                  "--kubeconfig", str(self.kubeconfig), "--alias", self.name,
                                  "--user-alias", self.name))
        os.chmod(self.kubeconfig, 0o600)
        self.check_kubeconfig(outputs)

    def check_kubeconfig(self, outputs=None):
        if not self.kubeconfig.is_file():
            raise ValueError("Generate the selected target kubeconfig first")
        outputs = outputs or self.load_outputs("infra")
        document = json.loads(self.run(["kubectl", "--kubeconfig", str(self.kubeconfig), "config", "view", "--raw", "-o", "json"], capture=True))
        context = next((c for c in document.get("contexts", []) if c["name"] == self.name), None)
        if not context:
            raise ValueError("Kubeconfig does not contain the selected context")
        cluster = next((c["cluster"] for c in document.get("clusters", []) if c["name"] == context["context"]["cluster"]), {})
        if cluster.get("server") != outputs["cluster_endpoint"]["value"] or cluster.get("certificate-authority-data") != outputs["cluster_ca"]["value"]:
            raise ValueError("Kubeconfig endpoint/CA does not match selected account outputs")

    def kubectl(self, arguments):
        self.reject_overrides(arguments, {"--kubeconfig", "--context", "--cluster", "--server", "-s", "--user", "--token", "--certificate-authority", "--insecure-skip-tls-verify"})
        self.check_account()
        self.check_kubeconfig()
        self.run(["kubectl", "--kubeconfig", str(self.kubeconfig), "--context", self.name, *arguments])

    def platform_inputs(self, image, ingress_cidrs=None, overwrite=False):
        outputs = self.load_outputs("infra")
        repository = outputs["ecr_repository_url"]["value"]
        if not image.startswith(repository + "@sha256:"):
            raise ValueError("Push/promote the image into this target account's ECR repository first")
        helper = load_helper("platform-inputs.py", "target_platform_inputs")
        value = helper.build_inputs(outputs, image, ingress_cidrs)
        self.scan_image(image)
        path = self.directory / "inputs" / "platform.tfvars.json"
        helper.write_private(path, value, overwrite=overwrite)
        print(f"Wrote {path}", file=sys.stderr)

    def scan_image(self, image, wait_seconds=300, account_checked=False):
        if not account_checked:
            self.check_account()
        helper = load_helper("image-security.py", "target_image_security")
        return helper.check_image(self, image, wait_seconds=wait_seconds)

    def demo(self):
        if self.environment != "dev":
            raise ValueError("The presentation demo is restricted to dev")
        outputs = self.load_outputs("platform")
        self.check_account()
        verify = load_helper("verify-live.py", "target_verify_live")
        print(outputs["application_url"]["value"])
        verify.check_http(outputs["application_url"]["value"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, choices=ENVIRONMENTS)
    parser.add_argument("--config", type=Path, help="Private config path; defaults to environments/<env>.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show")
    commands.add_parser("check")
    commands.add_parser("demo")
    commands.add_parser("kubeconfig")
    tf = commands.add_parser("terraform")
    tf.add_argument("stage", choices=STAGES)
    tf.add_argument("action", choices=("init", "plan", "apply", "output"))
    tf.add_argument("--destroy", action="store_true")
    tf.add_argument("--ingress-only", action="store_true")
    for command in ("aws", "kubectl"):
        commands.add_parser(command, add_help=False)
    platform = commands.add_parser("platform-inputs")
    platform.add_argument("--image", required=True)
    platform.add_argument("--ingress-cidr", action="append", dest="ingress_cidrs")
    platform.add_argument("--overwrite", action="store_true")
    scan = commands.add_parser("scan-image")
    scan.add_argument("--image", required=True, help="Selected ECR repository@sha256:digest")
    scan.add_argument("--wait-seconds", type=int, default=300, help="Wait for an initial scan (default: 300 seconds)")
    args, forwarded = parser.parse_known_args(argv)
    if args.command in ("aws", "kubectl"):
        args.arguments = forwarded
    elif forwarded:
        parser.error("unrecognized arguments: " + " ".join(forwarded))
    try:
        if args.command == "demo" and args.env != "dev":
            raise ValueError("The presentation demo is restricted to dev")
        target = Target(args.env, config_path=args.config)
        if args.command == "show":
            print(json.dumps({"environment": target.environment, "aws_account_id": target.account,
                              "aws_profile": target.profile, "region": target.region,
                              "cluster_name": target.name, "artifacts": str(target.directory)}, indent=2))
        elif args.command == "check":
            target.check_account()
        elif args.command == "terraform":
            target.terraform(args.stage, args.action, args.destroy, args.ingress_only)
        elif args.command in ("aws", "kubectl"):
            getattr(target, args.command)(args.arguments)
        elif args.command == "kubeconfig":
            target.create_kubeconfig()
        elif args.command == "platform-inputs":
            target.platform_inputs(args.image, args.ingress_cidrs, args.overwrite)
        elif args.command == "scan-image":
            target.scan_image(args.image, args.wait_seconds)
        elif args.command == "demo":
            target.demo()
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Target error: {error}\n")
    except subprocess.CalledProcessError as error:
        parser.exit(error.returncode, "Target command failed; inspect the command's diagnostic output.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
