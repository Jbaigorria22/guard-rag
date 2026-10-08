# CloudWatch log group where the container writes stdout/stderr.
# Creating the group is free; you only pay for ingested data.
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = 30

  tags = { Name = "${local.name_prefix}-logs" }
}
