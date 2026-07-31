# Daily source ingestion: DEFRA pre-formatted CSVs -> versioned raw S3 prefix.
# The Lambda runs independently of the EC2 host, so raw-data freshness does not
# depend on the dashboard server being online.

variable "s3_raw_prefix" {
  description = "Root S3 prefix for raw source data"
  type        = string
  default     = "raw"
}

variable "defra_site_folder" {
  description = "S3 folder below the raw prefix for London Bloomsbury data"
  type        = string
  default     = "defra/london_bloomsbury"
}

variable "defra_site_code" {
  description = "UK-AIR site code for London Bloomsbury"
  type        = string
  default     = "CLL2"
}

variable "defra_years_to_refresh" {
  description = "Number of recent years to refresh so provisional data revisions are captured"
  type        = number
  default     = 2

  validation {
    condition     = var.defra_years_to_refresh >= 1 && var.defra_years_to_refresh <= 5
    error_message = "defra_years_to_refresh must be between 1 and 5."
  }
}

variable "defra_ingest_schedule" {
  description = "EventBridge Scheduler expression for DEFRA ingestion"
  type        = string
  default     = "cron(30 5 * * ? *)"
}

variable "defra_ingest_timezone" {
  description = "Timezone used to evaluate the DEFRA ingestion schedule"
  type        = string
  default     = "Europe/London"
}

data "archive_file" "defra_ingest" {
  type        = "zip"
  source_file = "${path.module}/../lambda_src/defra_ingest.py"
  output_path = "${path.module}/.terraform/defra_ingest.zip"
}

resource "aws_cloudwatch_log_group" "defra_ingest" {
  name              = "/aws/lambda/${var.project_name}-defra-ingest"
  retention_in_days = 14

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role" "defra_ingest_lambda" {
  name = "${var.project_name}-defra-ingest-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role_policy" "defra_ingest_lambda" {
  name = "${var.project_name}-defra-ingest"
  role = aws_iam_role.defra_ingest_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListDefraPrefix"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.raw_data.arn
        Condition = {
          StringLike = {
            "s3:prefix" = "${var.s3_raw_prefix}/${var.defra_site_folder}/*"
          }
        }
      },
      {
        Sid    = "ReadAndWriteDefraObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.raw_data.arn}/${var.s3_raw_prefix}/${var.defra_site_folder}/*"
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.defra_ingest.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "defra_ingest" {
  function_name    = "${var.project_name}-defra-ingest"
  description      = "Downloads validated London Bloomsbury CSVs from DEFRA into S3"
  filename         = data.archive_file.defra_ingest.output_path
  source_code_hash = data.archive_file.defra_ingest.output_base64sha256
  role             = aws_iam_role.defra_ingest_lambda.arn
  handler          = "defra_ingest.lambda_handler"
  runtime          = "python3.13"
  timeout          = 120
  memory_size      = 128

  environment {
    variables = {
      S3_BUCKET        = aws_s3_bucket.raw_data.bucket
      S3_PREFIX        = "${var.s3_raw_prefix}/${var.defra_site_folder}"
      DEFRA_SITE_CODE  = var.defra_site_code
      YEARS_TO_REFRESH = tostring(var.defra_years_to_refresh)
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.defra_ingest,
    aws_iam_role_policy.defra_ingest_lambda,
    aws_s3_bucket_versioning.raw_data_versioning
  ]

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role" "defra_ingest_scheduler" {
  name = "${var.project_name}-defra-ingest-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "scheduler.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role_policy" "defra_ingest_scheduler" {
  name = "${var.project_name}-invoke-defra-ingest"
  role = aws_iam_role.defra_ingest_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.defra_ingest.arn
    }]
  })
}

resource "aws_scheduler_schedule" "defra_ingest" {
  name                         = "${var.project_name}-defra-ingest-daily"
  description                  = "Refresh London Bloomsbury current and previous-year CSVs in S3"
  schedule_expression          = var.defra_ingest_schedule
  schedule_expression_timezone = var.defra_ingest_timezone
  state                        = "ENABLED"

  depends_on = [aws_iam_role_policy.defra_ingest_scheduler]

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.defra_ingest.arn
    role_arn = aws_iam_role.defra_ingest_scheduler.arn
    input    = jsonencode({})

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "defra_ingest_errors" {
  alarm_name          = "${var.project_name}-defra-ingest-errors"
  alarm_description   = "The scheduled DEFRA ingestion Lambda returned an error"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.defra_ingest.function_name
  }

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

output "defra_ingest_lambda_name" {
  description = "Lambda function that refreshes DEFRA CSVs in S3"
  value       = aws_lambda_function.defra_ingest.function_name
}

output "defra_ingest_schedule_name" {
  description = "Daily EventBridge Scheduler schedule for DEFRA ingestion"
  value       = aws_scheduler_schedule.defra_ingest.name
}

output "defra_ingest_error_alarm_name" {
  description = "CloudWatch alarm that enters ALARM when ingestion fails"
  value       = aws_cloudwatch_metric_alarm.defra_ingest_errors.alarm_name
}
