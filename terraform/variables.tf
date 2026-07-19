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

variable "allowed_ip" {
  description = "Your public IP in CIDR format, e.g. 1.2.3.4/32"
  type        = string
}

variable "ssh_key_name" {
  description = "Existing AWS EC2 key pair name"
  type        = string
}

variable "ec2_instance_type" {
  description = "EC2 instance type for the Timescale/Grafana host. t3.micro is free-tier eligible; the pipeline runs one-shot with a swapfile (see user_data) to survive memory spikes on 1 GB."
  type        = string
  default     = "t3.micro"
}

variable "root_volume_size" {
  description = "Root EBS volume size in GB"
  type        = number
  default     = 20
}

variable "github_repository" {
  description = "GitHub repo (owner/name) allowed to assume the CI role via OIDC to push to ECR"
  type        = string
  default     = "Uche-anya/London-Environment-Time-Series"
}