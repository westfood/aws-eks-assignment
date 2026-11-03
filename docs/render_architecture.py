#!/usr/bin/env python3
"""Write the editable architecture SVG using only the Python standard library.

Run from any directory: python3 docs/render_architecture.py
The checked-in PNG is a raster export of this SVG, not a separate diagram.
"""

from html import escape
from pathlib import Path


OUT = Path(__file__).resolve().parent / "architecture.svg"
WIDTH, HEIGHT = 2160, 1360
C = {
    "ink": "#182c40", "muted": "#52677a", "line": "#b9c8d3",
    "blue": "#14669b", "purple": "#8653a4", "green": "#23775d",
    "public": "#e9f4fc", "compute": "#eaf5ef", "database": "#f0eef9",
    "paper": "#ffffff", "bg": "#f7fafc", "orange": "#9b621a",
}
parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<title>Contoso AWS DevOps demonstration architecture</title>
<desc>A two-Availability-Zone VPC with public ALB subnets, private EKS compute subnets and isolated RDS subnets. The diagram labels the Single-AZ database, shared NAT, conditional HTTPS and proposed static frontend explicitly.</desc>
<defs>
  <marker id="arrowBlue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{C['blue']}"/></marker>
  <marker id="arrowPurple" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{C['purple']}"/></marker>
  <marker id="arrowGrey" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{C['muted']}"/></marker>
</defs>
<style>
text {{ font-family: Arial, Helvetica, sans-serif; fill: {C['ink']}; }}
.title {{ font-size: 34px; font-weight: 700; }}
.subtitle {{ font-size: 19px; fill: {C['muted']}; }}
.section {{ font-size: 22px; font-weight: 700; }}
.label {{ font-size: 20px; font-weight: 700; }}
.body {{ font-size: 18px; }}
.small {{ font-size: 16px; fill: {C['muted']}; }}
.tiny {{ font-size: 15px; fill: {C['muted']}; }}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" fill="{C['bg']}"/>
''']


def rect(x, y, w, h, fill="white", stroke=None, radius=12, dash=None):
    stroke = stroke or C["line"]
    dashed = f' stroke-dasharray="{dash}"' if dash else ""
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"{dashed}/>')


def text(x, y, label, cls="body", anchor="start", fill=None):
    color = f' style="fill:{fill}"' if fill else ""
    parts.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"{color}>{escape(label)}</text>')


def lines(x, y, content, cls="body", step=28, anchor="start"):
    for index, label in enumerate(content):
        text(x, y + index * step, label, cls, anchor)


def path(d, color="blue", dashed=False, width=3, arrow=True):
    dash = ' stroke-dasharray="9 7"' if dashed else ""
    marker = f' marker-end="url(#arrow{ {"blue": "Blue", "purple": "Purple", "muted": "Grey"}[color] })"' if arrow else ""
    parts.append(f'<path d="{d}" fill="none" stroke="{C[color]}" stroke-width="{width}" stroke-linejoin="round"{dash}{marker}/>')


text(48, 60, "Contoso application platform", "title")
text(48, 98, "Terraform design • Two-AZ network • Private compute and database • Live AWS verification still required", "subtitle")

# VPC and AZ boundaries.
rect(350, 175, 1420, 940, C["paper"], C["blue"], 18)
text(375, 210, "VPC", "section", fill=C["blue"])
text(1738, 210, "EKS nodes and RDS have private addresses", "small", "end")
rect(380, 235, 650, 825, C["paper"], C["line"], 12, "8 6")
rect(1080, 235, 650, 825, C["paper"], C["line"], 12, "8 6")
text(405, 267, "Availability Zone A", "section")
text(1105, 267, "Availability Zone B", "section")

for x, suffix in [(400, "A"), (1100, "B")]:
    rect(x, 285, 610, 180, C["public"])
    rect(x, 495, 610, 250, C["compute"])
    rect(x, 775, 610, 240, C["database"])
    text(x + 18, 312, f"PUBLIC SUBNET {suffix}", "small")
    text(x + 18, 525, f"PRIVATE COMPUTE SUBNET {suffix}", "small")
    text(x + 18, 805, f"ISOLATED DATABASE SUBNET {suffix}", "small")

# External browser and application ingress.
rect(48, 285, 230, 112, C["paper"], C["blue"])
text(163, 323, "Browser", "label", "middle")
lines(163, 353, ["Frontend + JSON API", "Synthetic demo data"], "small", 24, "middle")
path("M 278 340 H 750")
lines(50, 430, ["HTTP 80: explicit client CIDRs", "HTTPS 443: owned domain", "and ACM certificate"], "tiny", 24)
rect(755, 325, 640, 85, C["paper"], C["blue"])
text(1075, 357, "Internet-facing ALB", "label", "middle")
text(1075, 387, "WAF managed rules + rate limit (configurable)", "small", "middle")
text(1413, 355, "Spans both", "tiny")
text(1413, 377, "public subnets", "tiny")

# One NAT Gateway, distinct from incoming requests.
rect(435, 365, 265, 70, C["paper"], C["purple"])
text(567, 393, "NAT Gateway", "label", "middle")
text(567, 419, "Single-AZ demo egress", "tiny", "middle")

# Private compute and desired placement.
for x in [440, 1140]:
    rect(x, 555, 510, 135, C["paper"], C["green"])
    text(x + 255, 590, "EKS worker + application Pod", "label", "middle")
    text(x + 255, 621, "Frontend and API share the deployment", "body", "middle")
    text(x + 255, 652, "Private IP • HTTP 8080 • /readyz health check", "small", "middle")
text(705, 724, "Node group spans compute subnets; Pod placement is illustrative", "tiny", "middle")
text(1405, 724, "No public node IP addresses", "tiny", "middle")
path("M 960 410 V 478 H 695 V 550")
path("M 1190 410 V 478 H 1395 V 550")
text(1080, 452, "HTTP 8080 to Pod IP targets", "small", "middle")

# DB and explicit empty AZ-B member.
rect(440, 840, 510, 125, C["paper"], C["purple"])
text(695, 875, "RDS PostgreSQL", "label", "middle")
text(695, 907, "Single-AZ demo instance", "body", "middle")
text(695, 939, "DB SG: EKS node SG → TCP 5432 only", "small", "middle")
rect(1140, 840, 510, 125, "#fbfaff", C["line"], 12, "7 6")
text(1395, 880, "DB subnet group member", "label", "middle")
lines(1395, 914, ["No standby in the Single-AZ demo", "No internet or NAT default route"], "small", 26, "middle")
path("M 695 690 V 835")
text(715, 774, "TCP 5432 + verified TLS", "small")
path("M 1395 690 V 758 H 990 V 902 H 955")
text(1080, 1038, "Application IAM login and SQL grants are additional controls", "small", "middle")

# Egress paths are drawn separately from requests.
path("M 440 628 H 418 V 435 H 455", "purple", width=2)
path("M 1650 628 H 1688 V 478 H 680 V 440", "purple", width=2)
text(487, 487, "Outbound image pulls / AWS APIs", "tiny", fill=C["purple"])

# Management and identity are outside the customer data path.
rect(48, 520, 230, 195, C["paper"])
text(68, 554, "Administrator", "label")
lines(68, 589, ["Terraform roots", "1  bootstrap: state", "2  infra: AWS", "3  platform: Helm/K8s"], "small", 28)
text(68, 701, "AWS identity + kubeconfig", "tiny")

rect(1810, 250, 302, 190, C["paper"], C["muted"], 12, "7 6")
text(1830, 287, "EKS control plane", "label")
lines(1830, 320, ["Managed by AWS", "Private API enabled", "Public API: admin CIDRs", "Private-only option needs", "a connected runner/network"], "small", 25)
path("M 48 600 H 24 V 150 H 1960 V 245", "muted", dashed=True, width=2)
text(1190, 143, "Management: Terraform, Helm and kubectl", "tiny", "middle")
path("M 1810 390 H 1750 V 585 H 1656", "muted", dashed=True, width=2)
text(1700, 475, "Private API", "tiny", "middle")

rect(1810, 485, 302, 250, C["paper"])
text(1830, 523, "Application identity", "label")
lines(1830, 561, ["Service account → IRSA", "Temporary AWS credentials", "rds-db:connect only", "for the app database user", "", "TLS: verify-full + RDS CA", "No master-secret access"], "small", 25)

rect(1810, 775, 302, 240, C["paper"])
text(1830, 813, "DB initialization", "label")
lines(1830, 851, ["Separate Job and IAM role", "Reads managed master", "secret from Secrets Manager", "Creates restricted app user", "and application schema", "Master-secret access is not", "granted to the serving role"], "small", 24)

# Legend and production proposal are visually distinct.
rect(48, 1160, 1722, 145, C["paper"])
text(72, 1195, "How to read this diagram", "label")
path("M 75 1227 H 135", width=3)
text(152, 1234, "Application requests and database traffic", "small")
path("M 760 1227 H 820", "purple", width=2)
text(837, 1234, "Private-node outbound traffic through NAT", "small")
path("M 75 1270 H 135", "muted", dashed=True, width=2)
text(152, 1277, "Management path; not the browser request path", "small")
text(837, 1277, "Two DB subnets do not imply a running standby", "small")

rect(1810, 1060, 302, 245, "#fff8ed", C["orange"], 12, "7 6")
text(1830, 1098, "Production options", "label", fill=C["orange"])
lines(1830, 1135, ["Proposed, not deployed here", "", "Private S3 + CloudFront", "for a larger static frontend", "Multi-AZ DB and AZ-local NAT", "Application authentication", "Owned DNS + verified HTTPS"], "small", 25)

parts.append("</svg>\n")
OUT.write_text("\n".join(parts), encoding="utf-8")
print(OUT)
