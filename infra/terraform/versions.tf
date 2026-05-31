terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state (configure per environment before init):
  # backend "s3" {
  #   bucket         = "p2-recommender-tfstate"
  #   key            = "dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "p2-recommender-tflock"
  #   encrypt        = true
  # }
}
