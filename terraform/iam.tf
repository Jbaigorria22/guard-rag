# IAM for the ECS task: two separate roles, least privilege.
#
#   execution role -> used by ECS itself to start the task
#                     (pull the image from ECR, write logs).
#   task role      -> used by YOUR code inside the container
#                     (call Amazon Bedrock). boto3 picks it up automatically.

data "aws_caller_identity" "current" {}

# The ECR repository was created with the AWS CLI; we only read it here.
data "aws_ecr_repository" "app" {
  name = "guard-rag"
}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # Must match config.py
  bedrock_chat_profile_id    = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
  bedrock_chat_base_model_id = "anthropic.claude-haiku-4-5-20251001-v1:0"
  bedrock_embed_model_id     = "amazon.titan-embed-text-v2:0"
}

# Trust policy: only the ECS tasks service, and only for tasks of THIS account
# (confused-deputy protection).
data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ecs:${var.aws_region}:${local.account_id}:*"]
    }
  }
}

# ---------------------------------------------------------------- execution role
resource "aws_iam_role" "task_execution" {
  name               = "${local.name_prefix}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "task_execution" {
  # GetAuthorizationToken does not support resource-level permissions.
  statement {
    sid       = "EcrAuthToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPullThisRepoOnly"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [data.aws_ecr_repository.app.arn]
  }

  statement {
    sid       = "WriteLogsToOurGroupOnly"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }
}

resource "aws_iam_role_policy" "task_execution" {
  name   = "ecr-pull-and-logs"
  role   = aws_iam_role.task_execution.id
  policy = data.aws_iam_policy_document.task_execution.json
}

# ------------------------------------------------------------------- task role
resource "aws_iam_role" "task" {
  name               = "${local.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "task_bedrock" {
  statement {
    sid    = "InvokeOnlyTheModelsTheAppUses"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      # Cross-region inference profile used for chat ...
      "arn:aws:bedrock:${var.aws_region}:${local.account_id}:inference-profile/${local.bedrock_chat_profile_id}",
      # ... which may route to the same model in other US regions.
      "arn:aws:bedrock:*::foundation-model/${local.bedrock_chat_base_model_id}",
      # Embeddings model.
      "arn:aws:bedrock:${var.aws_region}::foundation-model/${local.bedrock_embed_model_id}",
    ]
  }
}

resource "aws_iam_role_policy" "task_bedrock" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_bedrock.json
}
