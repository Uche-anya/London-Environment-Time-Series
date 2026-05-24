
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