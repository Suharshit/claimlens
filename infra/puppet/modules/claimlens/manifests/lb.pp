# @summary nginx load balancer built from facts and Hiera data.
class claimlens::lb (
  String        $app_name     = lookup('claimlens::app_name'),
  Integer       $app_port     = lookup('claimlens::app_port'),
  Array[String] $app_backends = lookup('app_backends'),
) {
  # custom function (functions/backend_list.pp) → ['10.0.0.5:8000', ...]
  $backends = claimlens::backend_list($app_backends, $app_port)

  package { 'nginx':
    ensure => installed,
  }

  file { '/etc/nginx/sites-available/default':
    ensure  => file,
    content => template('claimlens/lb.conf.erb'),
    require => Package['nginx'],
    notify  => Service['nginx'],
  }

  service { 'nginx':
    ensure => running,
    enable => true,
  }
}
