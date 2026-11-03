#!/usr/bin/env python3
"""Verify a deployed demo. Writes and a temporary deny probe require explicit flags."""

import argparse
import json
from pathlib import Path
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        old, new = urllib.parse.urlsplit(request.full_url), urllib.parse.urlsplit(new_url)
        if new.hostname != old.hostname or (old.scheme == "https" and new.scheme != "https"):
            raise ValueError("Refusing a redirect to a different host or a TLS downgrade")
        return super().redirect_request(request, fp, code, message, headers, new_url)


def check_http(base_url, write_message=False):
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Supply an http(s) application URL without embedded credentials")
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Supply the application's origin URL without a path, query or fragment")
    opener = urllib.request.build_opener(SafeRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def fetch(path, payload=None):
        encoded = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(base_url.rstrip("/") + path, data=encoded,
                                         headers={"Content-Type": "application/json", "User-Agent": "contoso-acceptance/1.0"})
        with opener.open(request, timeout=30) as response:
            return response.status, json.load(response)

    for endpoint, expected in (("/healthz", "healthy"), ("/readyz", "ready")):
        status, body = fetch(endpoint)
        if status != 200 or body.get("status") != expected:
            raise ValueError(f"{endpoint}: unexpected response")
        print(f"PASS {endpoint}: {expected}")
    status, body = fetch("/api/messages")
    if status != 200 or not isinstance(body.get("messages"), list):
        raise ValueError("GET /api/messages: unexpected response")
    print("PASS database-backed message read")
    if write_message:
        marker = "Synthetic acceptance check " + uuid.uuid4().hex
        status, created = fetch("/api/messages", {"body": marker})
        if status != 201 or created.get("message", {}).get("body") != marker:
            raise ValueError("POST /api/messages: unexpected response")
        _, reread = fetch("/api/messages")
        if not any(message.get("id") == created["message"]["id"] and message.get("body") == marker
                   for message in reread.get("messages", [])):
            raise ValueError("Saved synthetic message was not returned by a fresh read")
        print("PASS synthetic message write and fresh read (message retained in demo DB)")
    if parsed.scheme == "https":
        print("PASS HTTPS used system CA and hostname verification; no insecure TLS override")
    else:
        print("NOTE HTTP demo: no browser-to-ALB encryption; use only restricted clients and synthetic data")


def network_probe(kubeconfig, context, namespace):
    kubeconfig = Path(kubeconfig).resolve()
    if not kubeconfig.is_file():
        raise ValueError(f"Kubeconfig does not exist: {kubeconfig}")
    command = ["kubectl", "--kubeconfig", str(kubeconfig), "--context", context, "--namespace", namespace]

    def kubectl(*arguments, input_data=None, check=True):
        return subprocess.run(command + list(arguments), input=input_data, text=True,
                              capture_output=True, timeout=100, check=check)

    deployment = json.loads(kubectl("get", "deployment", "contoso-app", "-o", "json").stdout)
    container = next(item for item in deployment["spec"]["template"]["spec"]["containers"] if item["name"] == "app")
    environment = {item["name"]: item.get("value") for item in container.get("env", [])}
    host, port = environment.get("DB_HOST"), environment.get("DB_PORT", "5432")
    if not host:
        raise ValueError("Cannot find literal DB_HOST in deployed application container")
    # Standard VPC CNI policy mode may allow traffic briefly during Pod startup.
    # Wait before testing; DNS must succeed before a connection denial is accepted.
    code = """import os,socket,sys,time
time.sleep(8)
host,port=os.environ['PROBE_HOST'],int(os.environ['PROBE_PORT'])
socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
for attempt in range(3):
    try:
        connection=socket.create_connection((host,port),timeout=4)
    except (TimeoutError,socket.timeout):
        continue
    except OSError as error:
        sys.exit('INCONCLUSIVE: unexpected socket error '+str(error))
    else:
        connection.close()
        sys.exit('FAIL: Pod without allowed role label reached the database port')
print('EXPECTED DENY: DNS resolved; three database TCP attempts timed out')
"""
    name = "network-deny-probe-" + uuid.uuid4().hex[:10]
    pod_spec = {"restartPolicy": "Never", "automountServiceAccountToken": False, "activeDeadlineSeconds": 70,
                 "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "seccompProfile": {"type": "RuntimeDefault"}},
                 "containers": [{"name": "probe", "image": container["image"], "command": ["python", "-c", code],
                                 "env": [{"name": "PROBE_HOST", "value": host}, {"name": "PROBE_PORT", "value": str(port)}],
                                 "resources": {"requests": {"cpu": "50m", "memory": "32Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}},
                                 "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}}}]}
    # VPC CNI policy enforcement requires controller-owned Pods for reliability.
    job = {
        "apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": name, "namespace": namespace},
        "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 80,
                 "template": {"metadata": {"labels": {"role": "probe"}}, "spec": pod_spec}},
    }
    created = False
    try:
        kubectl("create", "-f", "-", input_data=json.dumps(job))
        created = True
        result = kubectl("wait", "--for=condition=complete", "--timeout=85s", "job/" + name, check=False)
        logs = kubectl("logs", "job/" + name, check=False)
        print(logs.stdout.strip())
        if result.returncode != 0 or logs.returncode != 0 or "EXPECTED DENY:" not in logs.stdout:
            raise ValueError("Deny probe did not succeed. Inspect Kubernetes events and policy enforcement; a timeout/ImagePull failure is inconclusive.")
        print("PASS expected NetworkPolicy denial observed. This is not a node-SG isolation or IAM authorization test.")
    finally:
        if created:
            deleted = kubectl("delete", "job", name, "--wait=true", "--timeout=30s", check=False)
            if deleted.returncode:
                print(f"Cleanup needed: delete Job {namespace}/{name} with the same kubeconfig/context", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--write-message", action="store_true", help="Persist one synthetic demo message")
    parser.add_argument("--check-networkpolicy", action="store_true", help="Create then delete a temporary deny-probe Job")
    parser.add_argument("--kubeconfig")
    parser.add_argument("--context")
    parser.add_argument("--namespace", default="contoso")
    args = parser.parse_args()
    if args.check_networkpolicy and not (args.kubeconfig and args.context):
        parser.error("--check-networkpolicy requires explicit --kubeconfig and --context")
    try:
        check_http(args.url, args.write_message)
        if args.check_networkpolicy:
            network_probe(args.kubeconfig, args.context, args.namespace)
            check_http(args.url)
    except (ValueError, OSError, urllib.error.URLError, subprocess.SubprocessError) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
