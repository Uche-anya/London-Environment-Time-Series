# -----------------------------
# ECR repository for the pipeline image
# -----------------------------
# GitHub Actions builds Dockerfile.pipeline and pushes here; the EC2 box pulls.
# Nothing is built on a laptop or on the t3.micro.

resource "aws_ecr_repository" "pipeline" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

# Keep the repo tidy: expire untagged images so old layers don't accumulate.
resource "aws_ecr_lifecycle_policy" "pipeline" {
  repository = aws_ecr_repository.pipeline.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      }
    ]
  })
}


# -----------------------------
# Let the EC2 instance PULL from ECR
# -----------------------------
# Attaches to the existing EC2 role (defined in main.tf) that already reads S3.

resource "aws_iam_policy" "ecr_pull_policy" {
  name        = "${var.project_name}-ecr-pull-policy"
  description = "Allows the EC2 host to pull the pipeline image from ECR"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = aws_ecr_repository.pipeline.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_ecr_pull_policy" {
  role       = aws_iam_role.ec2_s3_read_role.name
  policy_arn = aws_iam_policy.ecr_pull_policy.arn
}


# -----------------------------
# GitHub Actions OIDC -> IAM role (no long-lived keys in GitHub)
# -----------------------------

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions-ecr-push"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            # Only this GitHub repo (any branch/tag) may assume the role.
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:*"
          }
        }
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = "production"
  }
}

resource "aws_iam_role_policy" "github_actions_ecr_push" {
  name = "${var.project_name}-ecr-push"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = aws_ecr_repository.pipeline.arn
      }
    ]
  })
}
