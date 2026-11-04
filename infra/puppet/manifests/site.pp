# Classify nodes by the custom fact `node_role` (written by Ansible to /etc/node_role)
node default {
  include claimlens::base

  case $facts['node_role'] {
    'app':   { include claimlens::app }
    'lb':    { include claimlens::lb }
    default: { }
  }
}
