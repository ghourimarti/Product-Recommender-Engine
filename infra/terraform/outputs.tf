output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "dynamodb_table" {
  value = module.dynamodb.table_name
}

output "redis_endpoint" {
  value = module.redis.endpoint
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "artifacts_bucket" {
  value = module.s3.bucket
}
