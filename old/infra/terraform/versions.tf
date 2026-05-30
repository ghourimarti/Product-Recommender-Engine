terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state with locking (D15). Bootstrap the bucket + table once, then `terraform init`.
  backend "s3" {
    bucket         = "recommender-tfstate"          # override per-account via -backend-config
    key            = "recommender/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "recommender-tflock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "recommender"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
