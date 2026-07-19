
output "s3_bucket_name" {
  description = "Name of the raw data S3 bucket"
  value       = aws_s3_bucket.raw_data.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the raw data S3 bucket"
  value       = aws_s3_bucket.raw_data.arn
}

output "ec2_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_eip.app_eip.public_ip
}

output "airflow_url" {
  description = "Airflow UI URL"
  value       = "http://${aws_eip.app_eip.public_ip}:8080"
}

output "grafana_url" {
  description = "Grafana UI URL"
  value       = "http://${aws_eip.app_eip.public_ip}:3000"
}

output "ecr_repository_url" {
  description = "ECR repo the pipeline image is pushed to / pulled from (set as PIPELINE_IMAGE base)"
  value       = aws_ecr_repository.pipeline.repository_url
}

output "github_actions_role_arn" {
  description = "IAM role ARN GitHub Actions assumes via OIDC (set as the AWS_ROLE_ARN repo secret/variable)"
  value       = aws_iam_role.github_actions.arn
}