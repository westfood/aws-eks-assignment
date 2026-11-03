#!/usr/bin/env python3
"""Read-only, fail-closed ECR vulnerability gate for one selected target/digest.

Every invocation queries ECR again. The private JSON report is audit evidence,
not an authorization cache. This module never starts scans or changes findings.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL", "UNDEFINED")
WAITING_STATUSES = {"PENDING", "IN_PROGRESS"}
READY_STATUSES = {"COMPLETE", "ACTIVE"}
ON_PUSH_MAX_AGE_SECONDS = 24 * 60 * 60


class ImageSecurityError(ValueError):
    """The gate did not pass; report contains the persisted decision evidence."""

    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


class _ApiError(ValueError):
    def __init__(self, operation, code):
        super().__init__(f"ECR {operation} failed ({code}); image security was not verified")
        self.code = code


def _write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".image-security-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _api(target, operation, *arguments):
    command = target.aws_command("ecr", operation, *arguments, "--output", "json",
                                 "--no-cli-pager", "--no-paginate")
    try:
        output = target.run(command, capture=True)
    except subprocess.CalledProcessError as error:
        # AWS stderr can contain request details. Retain only the service's
        # symbolic error code, never arbitrary stderr or the command output.
        match = re.search(r"\(([A-Za-z][A-Za-z0-9]*Exception)\)", error.stderr or "")
        raise _ApiError(operation, match.group(1) if match else "request failed") from None
    except OSError:
        raise _ApiError(operation, "AWS CLI could not be executed") from None
    try:
        result = json.loads(output)
    except (TypeError, ValueError):
        raise ValueError(f"ECR {operation} returned invalid JSON") from None
    if not isinstance(result, dict):
        raise ValueError(f"ECR {operation} returned a malformed response")
    return result


def _selected_image(target, image):
    outputs = target.load_outputs("infra")
    selected = outputs.get("ecr_repository_url") if isinstance(outputs, dict) else None
    repository_url = selected.get("value") if isinstance(selected, dict) else None
    if not isinstance(repository_url, str):
        raise ValueError("Infrastructure outputs must include ecr_repository_url")
    hostname = f"{target.account}.dkr.ecr.{target.region}.amazonaws.com/"
    repository = repository_url.removeprefix(hostname)
    if (not repository_url.startswith(hostname) or not 2 <= len(repository) <= 256
            or not re.fullmatch(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*", repository)):
        raise ValueError("Infrastructure ECR URL belongs to another account/Region or is malformed")
    if not isinstance(image, str) or not re.fullmatch(re.escape(repository_url) + r"@sha256:[a-f0-9]{64}", image):
        raise ValueError("Image must be the selected infrastructure ECR repository@sha256:<64 lowercase hex characters>")
    return repository_url, repository, image.rsplit("@", 1)[1]


def _configuration(target, repository, required, report):
    registry = _api(target, "get-registry-scanning-configuration")
    if registry.get("registryId") != target.account:
        raise ValueError("ECR scanning configuration belongs to another account")
    settings = registry.get("scanningConfiguration")
    if not isinstance(settings, dict) or settings.get("scanType") not in {"BASIC", "ENHANCED"}:
        raise ValueError("ECR registry scan type is missing or unsupported")
    mode = settings["scanType"]
    report["scan_type"] = mode
    repositories = _api(target, "batch-get-repository-scanning-configuration",
                        "--repository-names", repository)
    configurations = repositories.get("scanningConfigurations")
    if repositories.get("failures") or not isinstance(configurations, list) or len(configurations) != 1:
        raise ValueError("ECR did not return the selected repository scanning configuration")
    configuration = configurations[0]
    arn = f"arn:aws:ecr:{target.region}:{target.account}:repository/{repository}"
    if (not isinstance(configuration, dict) or configuration.get("repositoryName") != repository
            or configuration.get("repositoryArn") != arn):
        raise ValueError("ECR repository scanning configuration does not match this target")
    frequency = configuration.get("scanFrequency")
    report["scan_frequency"] = frequency if isinstance(frequency, str) else None
    if frequency not in {"SCAN_ON_PUSH", "CONTINUOUS_SCAN"}:
        raise ValueError("Selected ECR repository must be scanned on push or continuously; MANUAL/OFF are not accepted")
    if mode == "BASIC" and frequency != "SCAN_ON_PUSH":
        raise ValueError("Basic ECR scanning must use SCAN_ON_PUSH")
    if required == "ENHANCED" and (mode != "ENHANCED" or frequency != "CONTINUOUS_SCAN"):
        raise ValueError("This environment requires ENHANCED scanning with CONTINUOUS_SCAN")
    return mode, frequency


def _timestamp(value, name):
    try:
        if isinstance(value, bool) or value is None:
            raise ValueError
        if isinstance(value, (int, float)):
            if not math.isfinite(value):
                raise ValueError
            parsed = datetime.fromtimestamp(value, timezone.utc)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
            parsed = parsed.astimezone(timezone.utc)
        else:
            raise ValueError
    except (ValueError, TypeError, OverflowError, OSError):
        raise ValueError(f"ECR {name} is missing or invalid") from None
    if parsed.timestamp() <= 0 or parsed.timestamp() > time.time() + 300:
        raise ValueError(f"ECR {name} is outside a valid time range")
    return parsed


def _severity_counts(value):
    if not isinstance(value, dict):
        raise ValueError("ECR findingSeverityCounts is missing or malformed")
    result = dict.fromkeys(SEVERITIES, 0)
    for severity, count in value.items():
        if severity not in result or isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("ECR findingSeverityCounts contains an invalid severity or count")
        result[severity] = count
    return result


def _validate_page(page, account, repository, digest):
    if (page.get("registryId") != account or page.get("repositoryName") != repository
            or not isinstance(page.get("imageId"), dict)
            or page["imageId"].get("imageDigest") != digest):
        raise ValueError("ECR scan response does not match the selected account/repository/digest")
    status = page.get("imageScanStatus")
    if not isinstance(status, dict) or not isinstance(status.get("status"), str):
        raise ValueError("ECR scan status is missing or malformed")
    return status["status"]


def _scan(target, repository, digest, mode, frequency, deadline, poll_seconds, report):
    announced = False
    while True:
        parameters = {"registryId": target.account, "repositoryName": repository,
                      "imageId": {"imageDigest": digest}, "maxResults": 1000}
        pages, tokens, findings = 0, set(), {}
        counts = dict.fromkeys(SEVERITIES, 0)
        pending = False
        completed = None
        source_updated = None
        while True:
            try:
                page = _api(target, "describe-image-scan-findings", "--cli-input-json", json.dumps(parameters))
            except _ApiError as error:
                if error.code != "ScanNotFoundException" or pages:
                    raise
                pending = True
                report["scan_status"] = "SCAN_NOT_FOUND"
                break
            pages += 1
            status = _validate_page(page, target.account, repository, digest)
            report["scan_status"] = status
            if status in WAITING_STATUSES:
                pending = True
                break
            if status == "UNSUPPORTED_IMAGE":
                raise ValueError("ECR cannot scan this image format/platform. For a multi-platform manifest index, select the supported linux/amd64 child image digest and scan that digest; preserve build provenance")
            if status not in READY_STATUSES:
                raise ValueError(f"ECR scan is not eligible/available: {status}")
            if status == "ACTIVE" and (mode != "ENHANCED" or frequency != "CONTINUOUS_SCAN"):
                raise ValueError("ECR ACTIVE scan status does not match the repository scanning configuration")
            if mode == "ENHANCED" and frequency == "CONTINUOUS_SCAN" and status != "ACTIVE":
                # A completed initial snapshot alone does not establish active
                # continuous coverage. Allow enrollment time, then fail closed.
                pending = True
                break
            details = page.get("imageScanFindings")
            if not isinstance(details, dict):
                raise ValueError("Completed ECR scan findings are missing")
            if details.get("imageScanCompletedAt") is None:
                pending = True
                break
            page_completed = _timestamp(details["imageScanCompletedAt"], "imageScanCompletedAt")
            page_source = details.get("vulnerabilitySourceUpdatedAt")
            page_source = _timestamp(page_source, "vulnerabilitySourceUpdatedAt") if page_source is not None else None
            if completed and (completed != page_completed or source_updated != page_source):
                raise ValueError("ECR scan changed during pagination; retry the security check")
            completed, source_updated = page_completed, page_source
            page_counts = _severity_counts(details.get("findingSeverityCounts"))
            # ECR can repeat image-wide summaries on every page. Never add them.
            for severity in SEVERITIES:
                counts[severity] = max(counts[severity], page_counts[severity])
            field = "enhancedFindings" if mode == "ENHANCED" else "findings"
            entries = details.get(field)
            if not isinstance(entries, list):
                raise ValueError(f"Completed ECR scan must contain an explicit {field} list")
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("severity") not in SEVERITIES:
                    raise ValueError("ECR returned a malformed vulnerability finding")
                if mode == "ENHANCED":
                    if entry.get("status") not in {"ACTIVE", "CLOSED", "SUPPRESSED"}:
                        raise ValueError("Enhanced ECR finding has a missing/invalid status")
                    if entry["status"] == "CLOSED":
                        continue
                    key = entry.get("findingArn")
                    if not isinstance(key, str) or not key:
                        raise ValueError("Enhanced ECR finding has no findingArn")
                else:
                    if not isinstance(entry.get("name"), str) or not entry["name"]:
                        raise ValueError("Basic ECR finding has no vulnerability name")
                    key = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
                # Suppressed findings still count when ECR returns them. An
                # approval/suppression is not an implicit release exception.
                previous = findings.get(key)
                if previous and previous != entry["severity"]:
                    raise ValueError("ECR finding severity changed during pagination; retry the security check")
                findings[key] = entry["severity"]
            token = page.get("nextToken")
            if token is None or token == "":
                break
            if not isinstance(token, str) or token in tokens or pages >= 10000:
                raise ValueError("ECR findings pagination is malformed or repeats a token")
            tokens.add(token)
            parameters["nextToken"] = token
        report["pages"] = pages
        if not pending:
            for severity in SEVERITIES:
                counts[severity] = max(counts[severity], sum(value == severity for value in findings.values()))
            report.update(finding_severity_counts=counts,
                          image_scan_completed_at=completed.isoformat(),
                          vulnerability_source_updated_at=source_updated.isoformat() if source_updated else None)
            if frequency == "SCAN_ON_PUSH" and time.time() - completed.timestamp() > ON_PUSH_MAX_AGE_SECONDS:
                raise ValueError("On-push ECR scan is older than 24 hours; obtain a fresh scan before deployment")
            if counts["CRITICAL"] or counts["HIGH"]:
                raise ValueError(f"ECR vulnerabilities block deployment: {counts['CRITICAL']} CRITICAL, {counts['HIGH']} HIGH")
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Timed out waiting for ECR scan completion and required coverage; image security was not verified")
        if not announced:
            print("Waiting for ECR scan completion and required coverage...", file=sys.stderr)
            announced = True
        time.sleep(min(poll_seconds, remaining))


def check_image(target, image, wait_seconds=300, poll_seconds=5):
    """Verify one image, persist evidence, and return its successful report.

    Failures persist a report then raise ImageSecurityError (a ValueError).
    Enhanced continuous freshness is event-driven: ACTIVE eligibility and a
    completed initial scan are required, without imposing the on-push 24-hour age.
    """
    report = {"schema_version": 1, "environment": target.environment,
              "aws_account_id": target.account, "aws_region": target.region,
              "checked_at": datetime.now(timezone.utc).isoformat(), "passed": False,
              "failure": None, "pages": 0, "scan_type": None, "scan_frequency": None,
              "finding_severity_counts": None, "image_scan_completed_at": None,
              "vulnerability_source_updated_at": None}
    path = Path(target.directory) / "image-security.json"
    try:
        if (isinstance(wait_seconds, bool) or not isinstance(wait_seconds, (int, float))
                or not math.isfinite(wait_seconds) or wait_seconds < 0
                or isinstance(poll_seconds, bool) or not isinstance(poll_seconds, (int, float))
                or not math.isfinite(poll_seconds) or poll_seconds <= 0):
            raise ValueError("Scan wait must be non-negative and polling interval must be positive")
        required = target.infra.get("ecr_scan_type", "BASIC")
        if required not in {"BASIC", "ENHANCED"}:
            raise ValueError("Environment ecr_scan_type must be BASIC or ENHANCED")
        report["required_scan_type"] = required
        repository_url, repository, digest = _selected_image(target, image)
        report.update(image=image, repository_url=repository_url, repository_name=repository,
                      image_digest=digest)
        path = Path(target.directory) / "image-scans" / f"{digest.removeprefix('sha256:')}.json"
        mode, frequency = _configuration(target, repository, required, report)
        report.update(scan_type=mode, scan_frequency=frequency)
        _scan(target, repository, digest, mode, frequency,
              time.monotonic() + wait_seconds, poll_seconds, report)
        report["passed"] = True
    except (ValueError, OSError, TypeError, KeyError) as error:
        report["failure"] = str(error) if isinstance(error, ValueError) else "Image security check could not read valid target/scan evidence"
        _write_report(path, report)
        raise ImageSecurityError(report["failure"], report) from None
    _write_report(path, report)
    print(f"Image security passed: {target.environment}, {mode}/{frequency}, 0 HIGH/CRITICAL ({digest[:19]}...)", file=sys.stderr)
    return report
