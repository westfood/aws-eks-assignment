data "aws_availability_zones" "available" { state = "available" }
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  azs       = slice(sort(data.aws_availability_zones.available.names), 0, 2)
  zones     = { for i, az in local.azs : tostring(i) => az }
  nat_zones = var.nat_per_az ? local.zones : { "0" = local.azs[0] }
  db_name   = "contoso"
  db_user   = "contoso_app"
  namespace = "contoso"
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = local.name }
}
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = local.name }
}
resource "aws_subnet" "public" {
  for_each                = local.zones
  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, tonumber(each.key))
  map_public_ip_on_launch = false
  tags = {
    Name                     = "${local.name}-public-${each.key}"
    "kubernetes.io/role/elb" = "1"
  }
}
resource "aws_subnet" "compute" {
  for_each                = local.zones
  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 10 + tonumber(each.key))
  map_public_ip_on_launch = false
  tags = {
    Name                              = "${local.name}-compute-${each.key}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}
resource "aws_subnet" "database" {
  for_each                = local.zones
  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.value
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 20 + tonumber(each.key))
  map_public_ip_on_launch = false
  tags                    = { Name = "${local.name}-database-${each.key}" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-public" }
}
resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}
resource "aws_route_table_association" "public" {
  for_each       = local.zones
  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public.id
}
resource "aws_eip" "nat" {
  for_each = local.nat_zones
  domain   = "vpc"
  tags     = { Name = "${local.name}-nat-${each.key}" }
}
resource "aws_nat_gateway" "main" {
  for_each      = local.nat_zones
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  depends_on    = [aws_internet_gateway.main]
  tags          = { Name = "${local.name}-nat-${each.key}" }
}
resource "aws_route_table" "compute" {
  for_each = local.zones
  vpc_id   = aws_vpc.main.id
  tags     = { Name = "${local.name}-compute-${each.key}" }
}
resource "aws_route" "compute_egress" {
  for_each               = local.zones
  route_table_id         = aws_route_table.compute[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[var.nat_per_az ? each.key : "0"].id
}
resource "aws_route_table_association" "compute" {
  for_each       = local.zones
  subnet_id      = aws_subnet.compute[each.key].id
  route_table_id = aws_route_table.compute[each.key].id
}
# Isolated database tier: the VPC-local route only, deliberately no NAT/IGW route.
resource "aws_route_table" "database" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-database-isolated" }
}
resource "aws_route_table_association" "database" {
  for_each       = local.zones
  subnet_id      = aws_subnet.database[each.key].id
  route_table_id = aws_route_table.database.id
}
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [for r in aws_route_table.compute : r.id]
  tags              = { Name = "${local.name}-s3" }
}
