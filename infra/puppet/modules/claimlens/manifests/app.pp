# @summary Keep the ClaimLens service running and its temp files cleaned.
#
# Only tmp/ is cleaned: state/ (claim records) and logs/ (the append-only
# run log) under the same data folder must never be deleted.
class claimlens::app (
  String  $app_name        = lookup('claimlens::app_name'),
  Integer $cleanup_minutes = lookup('claimlens::cleanup_minutes'),
) {
  service { $app_name:
    ensure => running,
    enable => true,
  }

  cron { "${app_name}-cleanup":
    command => "find /var/lib/${app_name}/tmp -type f -mmin +${cleanup_minutes} -delete",
    user    => 'root',
    minute  => '*/15',
  }
}
