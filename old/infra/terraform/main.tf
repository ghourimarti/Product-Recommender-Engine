locals {
  name = "recommender-${var.environment}"
  azs  = ["${var.region}a", "${var.region}b", "${var.region}c"]
}

# --- Network (D14) ---
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = var.environment != "prod" # cost: one NAT in non-prod
  enable_dns_hostnames = true

  tags = { "kubernetes.io/cluster/${local.name}" = "shared" }
}

# --- EKS (D15) ---
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = local.name
  cluster_version = var.cluster_version
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      desired_size   = var.node_desired_size
      min_size       = var.node_desired_size
      max_size       = var.node_max_size
    }
  }
}

# --- RDS Postgres (D1) ---
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier        = "${local.name}-pg"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage

  db_name  = "recommender"
  username = "recommender"
  port     = 5432

  multi_az               = var.environment == "prod"
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  manage_master_user_password = true # store in Secrets Manager (D17)
  skip_final_snapshot         = var.environment != "prod"
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name}-db"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "rds" {
  name_prefix = "${local.name}-rds-"
  vpc_id      = module.vpc.vpc_id
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
}

# --- ElastiCache Redis (D10) ---
resource "aws_elasticache_subnet_group" "this" {
  name       = "${local.name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.name}-redis"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [aws_security_group.rds.id]
}

# --- ECR (D15) ---
resource "aws_ecr_repository" "this" {
  for_each = toset(["recommender-backend", "recommender-frontend", "recommender-embedding"])
  name     = each.key
  image_scanning_configuration { scan_on_push = true }
}

# --- Secrets Manager (D17) ---
resource "aws_secretsmanager_secret" "app" {
  name = "${local.name}-app"
}

# --- Cost alert (Phase 5 hardening / D20) ---
variable "monthly_budget_usd" {
  type    = number
  default = 2500 # Phase-1 cost ceiling
}

variable "budget_alert_emails" {
  type    = list(string)
  default = []
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_alert_emails
  }
}

# --- Log retention (Phase 5 hardening) ---
resource "aws_cloudwatch_log_group" "app" {
  name              = "/recommender/${var.environment}"
  retention_in_days = var.environment == "prod" ? 90 : 14
}
