variable "repositories" {
  type = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)

  name = each.value

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

output "repository_urls" {
  value = { for key, repo in aws_ecr_repository.this : key => repo.repository_url }
}
