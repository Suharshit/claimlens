variable "project" {
  type    = string
  default = "claimlens"
}
variable "aws_region" {
  type    = string
  default = "ap-south-1"
}
variable "admin_cidr" {
  description = "Your public IP as x.x.x.x/32. Only this IP can SSH in or open the ops web UIs."
  type        = string
  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr must be your own IP as x.x.x.x/32, never 0.0.0.0/0."
  }
}
variable "app_port" {
  type    = number
  default = 8000
}
variable "app_count" {
  type    = number
  default = 2
}
variable "enable_lb" {
  type    = bool
  default = true
}
variable "enable_ops" {
  type    = bool
  default = true
}
variable "app_instance_type" {
  description = "1 GB is enough for the lean server install (requirements-server.txt, no PyTorch)."
  type        = string
  default     = "t3.micro"
}
variable "lb_instance_type" {
  type    = string
  default = "t3.micro"
}
variable "ops_instance_type" {
  description = "Puppet server (JVM) + Nagios need about 2 GB."
  type        = string
  default     = "t3.small"
}
variable "public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}
variable "private_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519"
}
