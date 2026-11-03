"""Credential-free helper tests; no AWS resources or Kubernetes API are contacted."""

import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inputs = load("platform_inputs", "platform-inputs.py")
verify = load("verify_live", "verify-live.py")


class PlatformInputsTests(unittest.TestCase):
    def outputs(self):
        values = {key: "example" for key in inputs.OUTPUTS.values()}
        values.update(environment="dev", aws_account_id="123456789012", admin_cidrs=["203.0.113.8/32"], certificate_arn="", app_hostname="", route53_zone_id="")
        return {key: {"value": value} for key, value in values.items()}

    def test_mapping_and_digest(self):
        result = inputs.build_inputs(self.outputs(), "example/image@sha256:" + "a" * 64)
        self.assertEqual(result["aws_region"], "example")
        self.assertEqual(result["replicas"], 2)
        self.assertNotIn("region", result)
        self.assertNotIn("ingress_cidrs", result)

    def test_rejects_tag_and_untrusted_public_http(self):
        with self.assertRaises(ValueError):
            inputs.build_inputs(self.outputs(), "example/image:latest")
        with self.assertRaises(ValueError):
            inputs.build_inputs(self.outputs(), "example/image@sha256:" + "a" * 64, ["0.0.0.0/0"])

    def test_public_https_requires_hostname_and_certificate(self):
        outputs = self.outputs()
        outputs["certificate_arn"]["value"] = "example-certificate"
        with self.assertRaises(ValueError):
            inputs.build_inputs(outputs, "example/image@sha256:" + "a" * 64, ["0.0.0.0/0"])
        outputs["app_hostname"]["value"] = "app.example.com"
        result = inputs.build_inputs(outputs, "example/image@sha256:" + "a" * 64, ["0.0.0.0/0"])
        self.assertEqual(result["ingress_cidrs"], ["0.0.0.0/0"])

    def test_private_write_and_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inputs.json"
            inputs.write_private(path, {"example": 1})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(ValueError):
                inputs.write_private(path, {"example": 2})
            inputs.write_private(path, {"example": 2}, overwrite=True)
            self.assertEqual(json.loads(path.read_text()), {"example": 2})


class VerificationTests(unittest.TestCase):
    def test_refuses_credentials_and_insecure_redirect(self):
        with self.assertRaises(ValueError):
            verify.check_http("https://user:password@app.example.com")
        import urllib.request
        request = urllib.request.Request("https://app.example.com/")
        with self.assertRaises(ValueError):
            verify.SafeRedirect().redirect_request(request, None, 302, "", {}, "http://app.example.com/")

    def test_network_probe_uses_controller_owned_job_and_cleans_up_on_failure(self):
        calls = []
        deployment = {"spec": {"template": {"spec": {"containers": [{"name": "app", "image": "repo@sha256:" + "a" * 64,
            "env": [{"name": "DB_HOST", "value": "example.rds.amazonaws.com"}]}]}}}}

        def run(command, **kwargs):
            calls.append((command, kwargs))
            if "deployment" in command:
                return subprocess.CompletedProcess(command, 0, json.dumps(deployment), "")
            if "wait" in command:
                return subprocess.CompletedProcess(command, 1, "", "timed out")
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            kubeconfig = Path(directory) / "kubeconfig"
            kubeconfig.write_text("not accessed by mocked subprocess")
            with patch.object(verify.subprocess, "run", side_effect=run):
                with self.assertRaises(ValueError):
                    verify.network_probe(kubeconfig, "dedicated-context", "contoso")
        create = next(call for call in calls if "create" in call[0])
        job = json.loads(create[1]["input"])
        self.assertEqual(job["kind"], "Job")
        self.assertEqual(job["spec"]["template"]["metadata"]["labels"], {"role": "probe"})
        self.assertFalse(job["spec"]["template"]["spec"]["automountServiceAccountToken"])
        self.assertTrue(any("delete" in call[0] and "job" in call[0] for call in calls))
        self.assertTrue(all("--context" in call[0] and "dedicated-context" in call[0] for call in calls))


if __name__ == "__main__":
    unittest.main()
