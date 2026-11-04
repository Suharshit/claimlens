terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.4"
    }
  }

  # Stage 5.4: uncomment for remote state (create the bucket first, then
  # terraform init -migrate-state). Owner call 2026-10-22: local state for now.
  # backend "s3" {
  #   bucket       = "__STATE_BUCKET__"
  #   key          = "claimlens/terraform.tfstate"
  #   region       = "ap-south-1"
  #   use_lockfile = true     # S3-native state locking (Terraform 1.10+)
  #   encrypt      = true
  # }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = var.project
      Env       = terraform.workspace
      ManagedBy = "terraform"
    }
  }
}

locals {
  env = terraform.workspace # dev, prod, ...

  nodes = merge(
    var.enable_lb ? { "lb-1" = { role = "lb", type = var.lb_instance_type } } : {},
    { for i in range(var.app_count) : "app-${i + 1}" => { role = "app", type = var.app_instance_type } },
    var.enable_ops ? { "ops-1" = { role = "ops", type = var.ops_instance_type } } : {}
  )
}

module "network" {
  source     = "./modules/network"
  project    = var.project
  env        = local.env
  admin_cidr = var.admin_cidr
  app_port   = var.app_port
}

module "compute" {
  source         = "./modules/compute"
  project        = var.project
  env            = local.env
  nodes          = local.nodes
  subnet_id      = module.network.subnet_id
  sg_by_role     = module.network.sg_by_role
  public_key     = file(pathexpand(var.public_key_path))
  root_volume_gb = 16
}

# Terraform → Ansible hand-off (Practical 15): write the inventory file
resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory/hosts.ini"
  file_permission = "0644"
  content = templatefile("${path.module}/inventory.tftpl", {
    nodes    = module.compute.nodes
    ssh_key  = pathexpand(var.private_key_path)
    ssh_user = "ubuntu"
  })
}
