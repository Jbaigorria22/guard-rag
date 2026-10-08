# Application Load Balancer: the only public entry point.
# Its security group lets in only your IP (see security_groups.tf).

resource "aws_lb" "main" {
  name                       = "${local.name_prefix}-alb"
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true

  # Lab environment: we destroy everything after testing.
  enable_deletion_protection = false

  tags = { Name = "${local.name_prefix}-alb" }
}

resource "aws_lb_target_group" "app" {
  name        = "${local.name_prefix}-tg"
  port        = 8501
  protocol    = "HTTP"
  target_type = "ip" # Fargate tasks register by IP
  vpc_id      = aws_vpc.main.id

  # Default is 300 s; a short drain makes `terraform destroy` much faster.
  deregistration_delay = 30

  health_check {
    path                = "/_stcore/health" # Streamlit health endpoint
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${local.name_prefix}-tg" }
}

# HTTP only: there is no domain/certificate yet (documented limitation).
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
