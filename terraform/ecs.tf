# ECS on Fargate: runs the container from the image stored in ECR.

locals {
  task_cpu    = 1024 # 1 vCPU
  task_memory = 2048 # 2 GB (Streamlit + ChromaDB + LangChain)
}

# Resolve the tag to its immutable digest, so Fargate runs exactly this image.
data "aws_ecr_image" "app" {
  repository_name = data.aws_ecr_repository.app.name
  image_tag       = var.image_tag
}

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name_prefix}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = local.task_cpu
  memory                   = local.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = "${data.aws_ecr_repository.app.repository_url}@${data.aws_ecr_image.app.image_digest}"
      essential = true

      portMappings = [{ containerPort = 8501, protocol = "tcp" }]

      environment = [
        { name = "AWS_REGION", value = var.aws_region },
        { name = "STREAMLIT_SERVER_HEADLESS", value = "true" },
        { name = "STREAMLIT_BROWSER_GATHER_USAGE_STATS", value = "false" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # Streamlit takes a while to boot; do not kill it for failing early checks.
  health_check_grace_period_seconds = 120

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8501
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [
    aws_lb_listener.http,
    aws_vpc_endpoint.interface,
    aws_vpc_endpoint.s3,
    aws_iam_role_policy.task_execution,
  ]
}
