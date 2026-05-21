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