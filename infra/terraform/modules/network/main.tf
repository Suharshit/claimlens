variable "project" { type = string }
variable "env" { type = string }
variable "admin_cidr" { type = string }
variable "app_port" { type = number }

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# SSH from the admin's IP only
resource "aws_security_group" "admin" {
  name   = "${var.project}-${var.env}-admin"
  vpc_id = data.aws_vpc.default.id
  ingress {
    description = "SSH from admin"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Private traffic inside the VPC: app port, Puppet 8140, NRPE 5666,
# and SSH 22 so Nagios on ops can run check_ssh against every node
resource "aws_security_group" "internal" {
  name   = "${var.project}-${var.env}-internal"
  vpc_id = data.aws_vpc.default.id
  dynamic "ingress" {
    for_each = toset([22, var.app_port, 8140, 5666])
    content {
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = [data.aws_vpc.default.cidr_block]
    }
  }
  # Nagios host check (check-host-alive) pings every node
  ingress {
    description = "ICMP echo from inside the VPC"
    from_port   = 8
    to_port     = 0
    protocol    = "icmp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
}

# Public web on the load balancer
resource "aws_security_group" "web" {
  name   = "${var.project}-${var.env}-web"
  vpc_id = data.aws_vpc.default.id
  dynamic "ingress" {
    for_each = toset([80, 443])
    content {
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }
}

output "subnet_id" {
  value = sort(data.aws_subnets.default.ids)[0]
}

output "sg_by_role" {
  value = {
    lb  = [aws_security_group.admin.id, aws_security_group.web.id, aws_security_group.internal.id]
    app = [aws_security_group.admin.id, aws_security_group.internal.id]
    ops = [aws_security_group.admin.id, aws_security_group.internal.id]
  }
}
