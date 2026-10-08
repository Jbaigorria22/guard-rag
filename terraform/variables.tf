variable "aws_region" {
  description = "Region de AWS."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nombre del proyecto."
  type        = string
  default     = "guard-rag"
}

variable "environment" {
  description = "Entorno."
  type        = string
  default     = "lab"
}

variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
  default     = "10.0.0.0/16"
}


variable "allowed_ingress_cidr" {
  description = "CIDR autorizado a llegar al ALB (tu IP publica con /32)."
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_ingress_cidr, 0)) && var.allowed_ingress_cidr != "0.0.0.0/0"
    error_message = "Usa un CIDR valido y nunca 0.0.0.0/0, que abre el ALB a todo internet."
  }
}

variable "image_tag" {
  description = "ECR image tag to deploy. It is resolved to an immutable digest at plan time."
  type        = string
  default     = "v2"
}
