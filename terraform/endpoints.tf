# VPC endpoints: private doorways from the private subnets to AWS services.
# The private subnets have NO route to the internet (no NAT gateway), so every
# AWS service the container talks to needs its own endpoint.

locals {
  interface_endpoints = {
    ecr_api         = "ecr.api"         # image metadata / auth
    ecr_dkr         = "ecr.dkr"         # image layers (registry API)
    logs            = "logs"            # CloudWatch Logs
    bedrock_runtime = "bedrock-runtime" # model invocation
  }
}

resource "aws_security_group" "endpoints" {
  name        = "${local.name_prefix}-endpoints-sg"
  description = "Interface endpoints: HTTPS only from the app containers"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-endpoints-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_from_app" {
  security_group_id            = aws_security_group.endpoints.id
  description                  = "HTTPS from the app containers"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_endpoints

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true

  tags = { Name = "${local.name_prefix}-${each.key}" }
}

# ECR stores image layers in S3. Gateway endpoints are free.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = { Name = "${local.name_prefix}-s3" }
}

# ------------------------------------------------ egress rules of the app SG
# Terraform removes the default allow-all egress rule, so the container can
# reach NOTHING until we allow it. Only these two destinations:

resource "aws_vpc_security_group_egress_rule" "app_to_endpoints" {
  security_group_id            = aws_security_group.app.id
  description                  = "HTTPS to the interface endpoints"
  referenced_security_group_id = aws_security_group.endpoints.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
}

resource "aws_vpc_security_group_egress_rule" "app_to_s3" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS to S3 (ECR image layers) through the gateway endpoint"
  prefix_list_id    = aws_vpc_endpoint.s3.prefix_list_id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
