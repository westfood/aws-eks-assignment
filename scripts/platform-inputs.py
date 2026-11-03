#!/usr/bin/env python3
"""Map Terraform infrastructure outputs to private platform inputs; no AWS calls."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile


OUTPUTS = {
    "aws_region": "region",
    **{key: key for key in (
        "cluster_name", "cluster_endpoint", "cluster_ca", "vpc_id",
        "public_subnet_ids", "public_subnet_cidrs", "database_subnet_cidrs",
        "database_host", "database_name", "database_user", "bootstrap_secret_arn",
        "app_role_arn", "bootstrap_role_arn", "controller_role_arn", "waf_acl_arn",
        "admin_cidrs", "certificate_arn", "app_hostname", "route53_zone_id",
    )},
}


def build_inputs(outputs, image, ingress_cidrs=None, replicas=2):
    if not re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", image):
        raise ValueError("Image must be repository@sha256:<64 lowercase hex characters>")
    if not 1 <= replicas <= 4:
        raise ValueError("Replicas must be between 1 and 4")
    try:
        result = {target: outputs[source]["value"] for target, source in OUTPUTS.items()}
    except (KeyError, TypeError) as error:
        raise ValueError(f"Missing/malformed Terraform output: {error}") from error
    if bool(result["certificate_arn"]) != bool(result["app_hostname"]):
        raise ValueError("A certificate and owned hostname must be supplied together")
    cidrs = ingress_cidrs if ingress_cidrs is not None else result["admin_cidrs"]
    for cidr in cidrs:
        network = ipaddress.ip_network(cidr, strict=True)
        if network.version != 4:
            raise ValueError("This deployment uses IPv4 ingress CIDRs")
        if network.prefixlen == 0 and not result["certificate_arn"]:
            raise ValueError("Internet-wide ingress requires a trusted HTTPS certificate/hostname")
    if not cidrs:
        raise ValueError("Supply at least one ingress CIDR")
    result.update(app_image=image, replicas=replicas)
    if ingress_cidrs is not None:
        result["ingress_cidrs"] = ingress_cidrs
    return result


def write_private(path, value, overwrite=False):
    path = Path(path)
    if path.exists() and not overwrite:
        raise ValueError(f"Refusing to replace {path}; use --overwrite after reviewing your existing inputs")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".platform-inputs-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--infra-outputs", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, default=Path("platform/terraform.tfvars.json"))
    parser.add_argument("--ingress-cidr", action="append", dest="ingress_cidrs")
    parser.add_argument("--replicas", type=int, default=2)
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()
    try:
        outputs = json.loads(arguments.infra_outputs.read_text())
        inputs = build_inputs(outputs, arguments.image, arguments.ingress_cidrs, arguments.replicas)
        write_private(arguments.output, inputs, arguments.overwrite)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Wrote {arguments.output} with mode 0600. Review it, then run terraform plan.")


if __name__ == "__main__":
    main()
