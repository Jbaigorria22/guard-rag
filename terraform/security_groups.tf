resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Firewall del balanceador: solo tu IP entra por HTTP"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-alb-sg" }
}

resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-app-sg"
  description = "Firewall del contenedor: solo el ALB entra al puerto 8501"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-app-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http_from_me" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP desde la IP autorizada"
  cidr_ipv4         = var.allowed_ingress_cidr
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_egress_rule" "alb_to_app" {
  security_group_id            = aws_security_group.alb.id
  description                  = "ALB hacia el contenedor"
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 8501
  to_port                      = 8501
}

resource "aws_vpc_security_group_ingress_rule" "app_from_alb" {
  security_group_id            = aws_security_group.app.id
  description                  = "Streamlit solo desde el ALB"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8501
  to_port                      = 8501
}