"""ECR release policy tests: all service responses and clocks are synthetic."""

from contextlib import redirect_stderr
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("image_security", Path(__file__).with_name("image-security.py"))
security = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(security)
NOW = 1_800_000_000
DIGEST = "sha256:" + "a" * 64
ACCOUNT = "123456789012"
REGION = "eu-central-1"
REPOSITORY = "contoso-dev-app"
URL = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPOSITORY}"
IMAGE = f"{URL}@{DIGEST}"


def scan_page(mode="BASIC", status=None, *, counts=None, findings=None, completed=NOW - 60):
    details = {"findingSeverityCounts": counts or {},
               "enhancedFindings" if mode == "ENHANCED" else "findings": findings or []}
    if completed is not None:
        details["imageScanCompletedAt"] = datetime.fromtimestamp(completed, timezone.utc).isoformat()
    return {"registryId": ACCOUNT, "repositoryName": REPOSITORY,
            "imageId": {"imageDigest": DIGEST},
            "imageScanStatus": {"status": status or ("ACTIVE" if mode == "ENHANCED" else "COMPLETE")},
            "imageScanFindings": details}


class FakeTarget:
    """ECR response boundary; a missing fake operation is always a test error."""

    environment, account, region = "dev", ACCOUNT, REGION

    def __init__(self, directory, mode="BASIC", frequency=None):
        self.directory = Path(directory)
        self.infra = {"ecr_scan_type": mode}
        self.outputs = {"ecr_repository_url": {"value": URL}}
        self.registry = {"registryId": ACCOUNT, "scanningConfiguration": {"scanType": mode}}
        self.repository = {"scanningConfigurations": [{
            "repositoryName": REPOSITORY,
            "repositoryArn": f"arn:aws:ecr:{REGION}:{ACCOUNT}:repository/{REPOSITORY}",
            "scanFrequency": frequency or ("CONTINUOUS_SCAN" if mode == "ENHANCED" else "SCAN_ON_PUSH"),
        }]}
        self.pages = [scan_page(mode)]
        self.calls = []

    def load_outputs(self, stage):
        if stage != "infra":
            raise AssertionError(f"Unexpected output root {stage}")
        return self.outputs

    def aws_command(self, *arguments):
        return ["aws", "--profile", "synthetic-dev", "--region", self.region, *arguments]

    def run(self, command, capture=False):
        self.calls.append(command)
        if not capture:
            raise AssertionError("Image gate must capture every read response")
        operation = command[command.index("ecr") + 1]
        if operation == "get-registry-scanning-configuration":
            result = self.registry
        elif operation == "batch-get-repository-scanning-configuration":
            result = self.repository
        elif operation == "describe-image-scan-findings":
            if not self.pages:
                raise AssertionError("Missing synthetic scan response")
            result = self.pages.pop(0)
        else:
            raise AssertionError(f"Unexpected AWS operation {operation}")
        if isinstance(result, Exception):
            raise result
        return json.dumps(result)


class ImageSecurityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ecr-policy-test-")
        self.addCleanup(temporary.cleanup)
        self.target = FakeTarget(temporary.name)
        for patcher in (
            patch.object(security.time, "time", return_value=NOW),
            patch.object(security.time, "sleep"),
            patch.object(security.subprocess, "run", side_effect=AssertionError("Real processes forbidden")),
            redirect_stderr(io.StringIO()),
        ):
            patcher.__enter__()
            self.addCleanup(patcher.__exit__, None, None, None)

    def check(self, **kwargs):
        return security.check_image(self.target, IMAGE, **kwargs)

    def report_path(self):
        return self.target.directory / "image-scans" / f"{DIGEST.removeprefix('sha256:')}.json"

    def test_completed_basic_scan_passes_and_preserves_private_evidence(self):
        report = self.check()
        self.assertTrue(report["passed"])
        self.assertEqual(report["image_digest"], DIGEST)
        self.assertEqual(report["scan_type"], "BASIC")
        self.assertEqual(report["finding_severity_counts"]["HIGH"], 0)
        self.assertEqual(json.loads(self.report_path().read_text()), report)
        self.assertEqual(stat.S_IMODE(self.report_path().stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.report_path().parent.stat().st_mode), 0o700)

    def test_every_check_reads_ecr_again_instead_of_trusting_cached_report(self):
        self.check()
        self.target.pages = [scan_page(counts={"HIGH": 1})]
        with self.assertRaisesRegex(security.ImageSecurityError, "1 HIGH"):
            self.check()
        self.assertEqual(sum("get-registry-scanning-configuration" in call for call in self.target.calls), 2)
        self.assertFalse(json.loads(self.report_path().read_text())["passed"])

    def test_high_and_critical_summary_counts_block_release(self):
        for severity in ("HIGH", "CRITICAL"):
            with self.subTest(severity=severity):
                self.target.pages = [scan_page(counts={severity: 1})]
                with self.assertRaisesRegex(security.ImageSecurityError, severity) as raised:
                    self.check()
                self.assertFalse(raised.exception.report["passed"])
                self.assertEqual(raised.exception.report["finding_severity_counts"][severity], 1)

    def test_findings_block_even_if_summary_understates_severity(self):
        self.target.pages = [scan_page(findings=[{"name": "CVE-SYNTHETIC", "severity": "HIGH"}])]
        with self.assertRaisesRegex(security.ImageSecurityError, "1 HIGH"):
            self.check()

    def test_pending_initial_scan_is_polled_until_complete(self):
        self.target.pages = [scan_page(status="IN_PROGRESS"), scan_page()]
        report = self.check(poll_seconds=0.001)
        self.assertTrue(report["passed"])
        requests = [call for call in self.target.calls if "describe-image-scan-findings" in call]
        self.assertEqual(len(requests), 2)
        for request in requests:
            parameters = json.loads(request[request.index("--cli-input-json") + 1])
            self.assertEqual(parameters["imageId"], {"imageDigest": DIGEST})

    def test_scan_not_found_waits_for_initial_scan_but_cannot_pass_alone(self):
        missing = subprocess.CalledProcessError(1, ["aws"], stderr="An error occurred (ScanNotFoundException)")
        self.target.pages = [missing, scan_page()]
        self.assertTrue(self.check(poll_seconds=0.001)["passed"])
        self.target.pages = [missing]
        with self.assertRaisesRegex(security.ImageSecurityError, "Timed out"):
            self.check(wait_seconds=0)

    def test_pending_scan_and_missing_initial_timestamp_fail_on_deadline(self):
        for page in (scan_page(status="PENDING"), scan_page(completed=None)):
            with self.subTest(page=page):
                self.target.pages = [page]
                with self.assertRaisesRegex(security.ImageSecurityError, "Timed out"):
                    self.check(wait_seconds=0)

    def test_completed_response_needs_explicit_counts_and_finding_list(self):
        for field in ("findingSeverityCounts", "findings"):
            with self.subTest(field=field):
                page = scan_page()
                del page["imageScanFindings"][field]
                self.target.pages = [page]
                with self.assertRaises(security.ImageSecurityError):
                    self.check()

    def test_invalid_counts_fail_closed(self):
        for counts in ({"HIGH": -1}, {"HIGH": True}, {"HIGH": "0"}, {"FUTURE": 1}):
            with self.subTest(counts=counts):
                self.target.pages = [scan_page(counts=counts)]
                with self.assertRaisesRegex(security.ImageSecurityError, "invalid severity or count"):
                    self.check()

    def test_basic_scan_older_than_24_hours_is_rejected(self):
        self.target.pages = [scan_page(completed=NOW - 86401)]
        with self.assertRaisesRegex(security.ImageSecurityError, "older than 24 hours"):
            self.check()

    def test_failed_ineligible_or_unsupported_scan_is_never_clean(self):
        for status in ("FAILED", "UNSUPPORTED_IMAGE", "SCAN_ELIGIBILITY_EXPIRED", "FINDINGS_UNAVAILABLE"):
            with self.subTest(status=status):
                self.target.pages = [scan_page(status=status)]
                with self.assertRaises(security.ImageSecurityError) as raised:
                    self.check()
                self.assertEqual(raised.exception.report["scan_status"], status)

    def test_service_error_report_does_not_leak_arbitrary_stderr(self):
        self.target.pages = [subprocess.CalledProcessError(1, ["aws"], stderr="private-token (AccessDeniedException)")]
        with self.assertRaisesRegex(security.ImageSecurityError, "AccessDeniedException") as raised:
            self.check()
        self.assertNotIn("private-token", str(raised.exception))
        self.assertNotIn("private-token", self.report_path().read_text())

    def test_all_pages_are_read_and_summary_counts_are_not_added(self):
        first = scan_page(counts={"MEDIUM": 2}, findings=[{"name": "CVE-1", "severity": "MEDIUM"}])
        first["nextToken"] = "synthetic-token"
        second = scan_page(counts={"MEDIUM": 2}, findings=[{"name": "CVE-2", "severity": "MEDIUM"}])
        self.target.pages = [first, second]
        report = self.check()
        self.assertEqual(report["pages"], 2)
        self.assertEqual(report["finding_severity_counts"]["MEDIUM"], 2)
        last = self.target.calls[-1]
        self.assertIn("--no-paginate", last)
        parameters = json.loads(last[last.index("--cli-input-json") + 1])
        self.assertEqual(parameters["nextToken"], "synthetic-token")
        self.assertEqual(parameters["maxResults"], 1000)

    def test_high_finding_on_later_page_blocks_release(self):
        first = scan_page()
        first["nextToken"] = "page-two"
        self.target.pages = [first, scan_page(findings=[{"name": "CVE-LATER", "severity": "HIGH"}])]
        with self.assertRaisesRegex(security.ImageSecurityError, "1 HIGH"):
            self.check()

    def test_repeated_page_token_and_changed_scan_are_rejected(self):
        for second in (scan_page(), scan_page(completed=NOW - 120)):
            first = scan_page()
            first["nextToken"] = "same-token"
            second["nextToken"] = "same-token"
            self.target.pages = [first, second]
            with self.subTest(second=second), self.assertRaisesRegex(security.ImageSecurityError, "pagination"):
                self.check()

    def test_scan_response_cannot_switch_account_repository_or_digest(self):
        for key, wrong in (("registryId", "999999999999"), ("repositoryName", "foreign"),
                           ("imageId", {"imageDigest": "sha256:" + "b" * 64})):
            page = scan_page()
            page[key] = wrong
            self.target.pages = [page]
            with self.subTest(key=key), self.assertRaisesRegex(security.ImageSecurityError, "does not match"):
                self.check()

    def test_image_identity_requires_selected_repository_and_full_digest(self):
        for image in (URL + ":latest", IMAGE.replace(ACCOUNT, "999999999999"), IMAGE[:-1], IMAGE.upper()):
            with self.subTest(image=image), self.assertRaises(security.ImageSecurityError):
                security.check_image(self.target, image)
        self.assertEqual(self.target.calls, [])

    def test_live_registry_and_repository_identity_must_match_target(self):
        self.target.registry["registryId"] = "999999999999"
        with self.assertRaisesRegex(security.ImageSecurityError, "another account"):
            self.check()
        self.target.registry["registryId"] = ACCOUNT
        self.target.repository["scanningConfigurations"][0]["repositoryArn"] = "arn:aws:ecr:us-east-1:999999999999:repository/foreign"
        with self.assertRaisesRegex(security.ImageSecurityError, "does not match"):
            self.check()

    def test_manual_or_off_repository_scanning_is_rejected(self):
        for frequency in ("MANUAL", "OFF"):
            self.target.repository["scanningConfigurations"][0]["scanFrequency"] = frequency
            with self.subTest(frequency=frequency), self.assertRaisesRegex(security.ImageSecurityError, "MANUAL/OFF"):
                self.check()

    def enhanced(self):
        self.target = FakeTarget(self.target.directory, "ENHANCED")

    def test_enhanced_active_scan_accepts_old_initial_timestamp(self):
        self.enhanced()
        self.target.pages = [scan_page("ENHANCED", completed=NOW - 30 * 86400)]
        self.assertTrue(self.check()["passed"], "Continuous scans are event-driven, not subject to Basic's 24-hour policy")

    def test_enhanced_continuous_complete_waits_for_active_coverage(self):
        self.enhanced()
        self.target.pages = [scan_page("ENHANCED", status="COMPLETE"), scan_page("ENHANCED", status="ACTIVE")]
        self.assertTrue(self.check(poll_seconds=0.001)["passed"])
        self.assertEqual(sum("describe-image-scan-findings" in call for call in self.target.calls), 2)

    def test_enhanced_continuous_complete_alone_cannot_pass(self):
        self.enhanced()
        self.target.pages = [scan_page("ENHANCED", status="COMPLETE")]
        with self.assertRaisesRegex(security.ImageSecurityError, "Timed out"):
            self.check(wait_seconds=0)

    def test_enhanced_requires_continuous_coverage_and_completed_initial_scan(self):
        self.enhanced()
        self.target.repository["scanningConfigurations"][0]["scanFrequency"] = "SCAN_ON_PUSH"
        with self.assertRaisesRegex(security.ImageSecurityError, "CONTINUOUS_SCAN"):
            self.check()
        self.enhanced()
        self.target.pages = [scan_page("ENHANCED", completed=None)]
        with self.assertRaisesRegex(security.ImageSecurityError, "Timed out"):
            self.check(wait_seconds=0)

    def test_enhanced_requirement_cannot_be_satisfied_by_actual_basic_scan(self):
        self.target.infra["ecr_scan_type"] = "ENHANCED"
        with self.assertRaisesRegex(security.ImageSecurityError, "requires ENHANCED"):
            self.check()

    def test_basic_requirement_accepts_stronger_enhanced_coverage(self):
        self.enhanced()
        self.target.infra["ecr_scan_type"] = "BASIC"
        self.assertTrue(self.check()["passed"])

    def test_basic_requirement_accepts_fresh_enhanced_scan_on_push(self):
        self.target = FakeTarget(self.target.directory, "ENHANCED", "SCAN_ON_PUSH")
        self.target.infra["ecr_scan_type"] = "BASIC"
        self.target.pages = [scan_page("ENHANCED", status="COMPLETE")]
        self.assertTrue(self.check()["passed"])

    def test_basic_requirement_rejects_stale_enhanced_scan_on_push(self):
        self.target = FakeTarget(self.target.directory, "ENHANCED", "SCAN_ON_PUSH")
        self.target.infra["ecr_scan_type"] = "BASIC"
        self.target.pages = [scan_page("ENHANCED", status="COMPLETE", completed=NOW - 86401)]
        with self.assertRaisesRegex(security.ImageSecurityError, "older than 24 hours"):
            self.check()

    def test_enhanced_suppressed_high_is_blocking_but_closed_is_not(self):
        self.enhanced()
        finding = {"findingArn": "arn:aws:inspector2:eu-central-1:123456789012:finding/synthetic",
                   "severity": "HIGH", "status": "SUPPRESSED"}
        self.target.pages = [scan_page("ENHANCED", findings=[finding])]
        with self.assertRaisesRegex(security.ImageSecurityError, "1 HIGH"):
            self.check()
        finding["status"] = "CLOSED"
        self.target.pages = [scan_page("ENHANCED", findings=[finding])]
        self.assertTrue(self.check()["passed"])


if __name__ == "__main__":
    unittest.main()
