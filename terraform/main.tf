
resource "aws_s3_bucket" "raw_data" {
  bucket = var.s3_bucket_name

  tags = {
    Name        = "${var.project_name}-raw-data"
    Environment = "production"
    Project     = var.project_name
  }
}

resource "aws_s3_bucket_public_access_block" "raw_data_public_access" {
  bucket = aws_s3_bucket.raw_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "raw_data_versioning" {
  bucket = aws_s3_bucket.raw_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_data_encryption" {
  bucket = aws_s3_bucket.raw_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical Ubuntu official AWS account

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}


resource "aws_iam_role" "ec2_s3_read_role" {
  name = "${var.project_name}-ec2-s3-read-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_policy" "s3_read_policy" {
  name        = "${var.project_name}-s3-read-policy"
  description = "Allows EC2-hosted Airflow to read raw DEFRA files from S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.raw_data.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.raw_data.arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_s3_read_policy" {
  role       = aws_iam_role.ec2_s3_read_role.name
  policy_arn = aws_iam_policy.s3_read_policy.arn
}

resource "aws_iam_instance_profile" "ec2_instance_profile" {
  name = "${var.project_name}-ec2-instance-profile"
  role = aws_iam_role.ec2_s3_read_role.name
}


# -----------------------------
# Security group
# -----------------------------

resource "aws_security_group" "app_sg" {
  name        = "${var.project_name}-app-sg"
  description = "Allow SSH, Airflow and Grafana access"

  ingress {
    description = "SSH from allowed IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ip]
  }

  ingress {
    description = "Airflow UI from allowed IP"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ip]
  }

  ingress {
    description = "Grafana UI from allowed IP"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ip]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-app-sg"
    Project     = var.project_name
    Environment = "production"
  }
}



resource "aws_instance" "app_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.ec2_instance_type
  key_name               = var.ssh_key_name
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_instance_profile.name

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
  }

  # Slim free-tier host: Docker + a swapfile. No Airflow/Astro here — the stack
  # is timescaledb + grafana + a one-shot pipeline run (docker-compose.prod.yml).
  # The 2 GB swap lets the one-time pipeline run (pandas/DuckDB/GX) survive memory
  # spikes on a 1 GB t3.micro; it's slower under swap but this is a batch job.
  user_data = <<-EOF
              #!/bin/bash
              set -e

              # git/curl/unzip/awscli are in Ubuntu's repos; Docker (engine + the
              # compose plugin) is NOT — install it from Docker's official script,
              # otherwise `docker-compose-plugin` fails to resolve via apt.
              apt-get update -y
              apt-get install -y git curl unzip awscli
              curl -fsSL https://get.docker.com | sh

              systemctl enable docker
              systemctl start docker
              usermod -aG docker ubuntu

              # 2 GB swap so the one-shot pipeline run doesn't OOM on 1 GB RAM.
              if [ ! -f /swapfile ]; then
                fallocate -l 2G /swapfile
                chmod 600 /swapfile
                mkswap /swapfile
                swapon /swapfile
                echo '/swapfile none swap sw 0 0' >> /etc/fstab
              fi
              EOF

  tags = {
    Name        = "${var.project_name}-ec2"
    Project     = var.project_name
    Environment = "production"
  }
}


resource "aws_eip" "app_eip" {
  instance = aws_instance.app_server.id
  domain   = "vpc"

  tags = {
    Name        = "${var.project_name}-eip"
    Project     = var.project_name
    Environment = "production"
  }
}