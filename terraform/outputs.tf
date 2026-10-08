output "app_url" {
  description = "Where the app is reachable (HTTP, your IP only)."
  value       = "http://${aws_lb.main.dns_name}"
}

output "deployed_image" {
  description = "Image digest running in Fargate."
  value       = data.aws_ecr_image.app.image_digest
}
