# Daily source ingestion: Open-Meteo ERA5 JSON -> versioned raw S3 prefix.

variable "weather_site_folder" {
  description = "S3 folder below the raw prefix for Open-Meteo weather data"
  type        = string
  default     = "open_meteo"
}

variable "weather_latitude" {
  description = "Latitude of the London Bloomsbury monitoring site"
  type        = string
  default     = "51.522290"
}

variable "weather_longitude" {
  description = "Longitude of the London Bloomsbury monitoring site"
  type        = string
  default     = "-0.125889"
}

variable "weather_start_date" {
  description = "First date included in the Open-Meteo backfill"
  type        = string
  default     = "2022-01-01"
}

variable "weather_model" {
  description = "Open-Meteo historical model; ERA5 provides a consistent long-term series"
  type        = string
  default     = "era5"
}

variable "weather_archive_lag_days" {
  description = "Days excluded from the moving head while ERA5 data is published"
  type        = number
  default     = 5

  validation {
    condition     = var.weather_archive_lag_days >= 1 && var.weather_archive_lag_days <= 14
    error_message = "weather_archive_lag_days must be between 1 and 14."
  }
}

variable "weather_years_to_refresh" {
  description = "Number of recent weather years fetched again to capture revisions"
  type        = number
  default     = 2

  validation {
    condition     = var.weather_years_to_refresh >= 1 && var.weather_years_to_refresh <= 5
    error_message = "weather_years_to_refresh must be between 1 and 5."
  }
}

variable "weather_ingest_schedule" {
  description = "EventBridge Scheduler expression for Open-Meteo ingestion"
  type        = string
  default     = "cron(20 5 * * ? *)"
}

variable "weather_ingest_timezone" {
  description = "Timezone used to evaluate the weather ingestion schedule"
  type        = string
  default     = "Europe/London"
}

data "archive_file" "weather_ingest" {
  type        = "zip"
  source_file = "${path.module}/../lambda_src/weather_ingest.py"
  output_path = "${path.module}/.terraform/weather_ingest.zip"
}

resource "aws_cloudwatch_log_group" "weather_ingest" {
  name              = "/aws/lambda/${var.project_name}-weather-ingest"
  retention_in_days = 14

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role" "weather_ingest_lambda" {
  name = "${var.project_name}-weather-ingest-lambda"

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

resource "aws_iam_role_policy" "weather_ingest_lambda" {
  name = "${var.project_name}-weather-ingest"
  role = aws_iam_role.weather_ingest_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListWeatherPrefix"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.raw_data.arn
        Condition = {
          StringLike = {
            "s3:prefix" = "${var.s3_raw_prefix}/${var.weather_site_folder}/*"
          }
        }
      },
      {
        Sid    = "ReadAndWriteWeatherObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.raw_data.arn}/${var.s3_raw_prefix}/${var.weather_site_folder}/*"
      },
      {
        Sid    = "WriteLambdaLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.weather_ingest.arn}:*"
      }
    ]
  })
}

resource "aws_lambda_function" "weather_ingest" {
  function_name    = "${var.project_name}-weather-ingest"
  description      = "Downloads validated London Bloomsbury ERA5 weather into S3"
  filename         = data.archive_file.weather_ingest.output_path
  source_code_hash = data.archive_file.weather_ingest.output_base64sha256
  role             = aws_iam_role.weather_ingest_lambda.arn
  handler          = "weather_ingest.lambda_handler"
  runtime          = "python3.13"
  timeout          = 300
  memory_size      = 256

  environment {
    variables = {
      S3_BUCKET        = aws_s3_bucket.raw_data.bucket
      S3_PREFIX        = "${var.s3_raw_prefix}/${var.weather_site_folder}"
      LATITUDE         = var.weather_latitude
      LONGITUDE        = var.weather_longitude
      START_DATE       = var.weather_start_date
      TIMEZONE         = "GMT"
      WEATHER_MODEL    = var.weather_model
      ARCHIVE_LAG_DAYS = tostring(var.weather_archive_lag_days)
      YEARS_TO_REFRESH = tostring(var.weather_years_to_refresh)
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.weather_ingest,
    aws_iam_role_policy.weather_ingest_lambda,
    aws_s3_bucket_versioning.raw_data_versioning
  ]

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role" "weather_ingest_scheduler" {
  name = "${var.project_name}-weather-ingest-scheduler"

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

resource "aws_iam_role_policy" "weather_ingest_scheduler" {
  name = "${var.project_name}-invoke-weather-ingest"
  role = aws_iam_role.weather_ingest_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.weather_ingest.arn
    }]
  })
}

resource "aws_scheduler_schedule" "weather_ingest" {
  name                         = "${var.project_name}-weather-ingest-daily"
  description                  = "Refresh Open-Meteo ERA5 weather JSON in S3"
  schedule_expression          = var.weather_ingest_schedule
  schedule_expression_timezone = var.weather_ingest_timezone
  state                        = "ENABLED"

  depends_on = [aws_iam_role_policy.weather_ingest_scheduler]

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.weather_ingest.arn
    role_arn = aws_iam_role.weather_ingest_scheduler.arn
    input    = jsonencode({})

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "weather_ingest_errors" {
  alarm_name          = "${var.project_name}-weather-ingest-errors"
  alarm_description   = "The scheduled Open-Meteo ingestion Lambda returned an error"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.weather_ingest.function_name
  }

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

output "weather_ingest_lambda_name" {
  description = "Lambda function that refreshes Open-Meteo weather in S3"
  value       = aws_lambda_function.weather_ingest.function_name
}

output "weather_ingest_schedule_name" {
  description = "Daily EventBridge Scheduler schedule for weather ingestion"
  value       = aws_scheduler_schedule.weather_ingest.name
}

output "weather_ingest_error_alarm_name" {
  description = "CloudWatch alarm that enters ALARM when weather ingestion fails"
  value       = aws_cloudwatch_metric_alarm.weather_ingest_errors.alarm_name
}
