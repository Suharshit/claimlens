output "nodes" {
  value = module.compute.nodes
}
output "site_url" {
  value = var.enable_lb ? "http://${module.compute.nodes["lb-1"].public_ip}" : "http://${module.compute.nodes["app-1"].public_ip}:${var.app_port}"
}
output "nagios_tunnel" {
  value = var.enable_ops ? "ssh -L 8090:localhost:80 ubuntu@${module.compute.nodes["ops-1"].public_ip}  then open http://localhost:8090/nagios4" : "ops node disabled"
}
