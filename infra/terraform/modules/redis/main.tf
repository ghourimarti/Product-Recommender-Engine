variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "redis" {
  name   = "${var.name}-redis-sg"
  vpc_id = var.vpc_id
  tags   = var.tags
}

# Multi-AZ Redis: cache + queue broker, replicas across AZs.
resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = "${var.name}-redis"
  description                = "Redis for ${var.name}"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.redis.id]
  tags                       = var.tags
}

output "endpoint" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}
