# Terraform — recommender infrastructure (Decision 14/15)

Provisions VPC, EKS, RDS Postgres, ElastiCache Redis, ECR, Secrets Manager.

## Usage
```bash
# One-time: create the state bucket + lock table, then:
terraform init -backend-config="bucket=<your-tfstate-bucket>"
terraform fmt -check
terraform validate
terraform plan  -var-file=dev.tfvars   # review (Phase 6 gate: no apply yet)
terraform apply -var-file=dev.tfvars
```

## Structure
| File | Purpose |
|---|---|
| `versions.tf` | provider + S3 remote state w/ DynamoDB lock |
| `variables.tf` | tunables (region, sizes, env) |
| `main.tf` | vpc / eks / rds / elasticache / ecr / secrets |
| `outputs.tf` | cluster, db, redis, ECR URLs, secret ARN |

Per-env: `dev.tfvars`, `staging.tfvars`, `prod.tfvars` (prod sets `multi_az`, more nodes).
Qdrant runs in-cluster via Helm (or use Qdrant Cloud); not managed here.
