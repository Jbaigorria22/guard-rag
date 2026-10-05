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