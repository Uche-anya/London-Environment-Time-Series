variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "london-environment-pipeline"
}

variable "s3_bucket_name" {
  description = "Globally unique S3 bucket name"
  type        = string
}