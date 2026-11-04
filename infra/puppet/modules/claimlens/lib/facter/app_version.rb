# Which ClaimLens version is deployed (from the "current" symlink target).
Facter.add(:app_version) do
  setcode do
    link = '/opt/claimlens/current'
    File.symlink?(link) ? File.basename(File.readlink(link)).sub(/^claimlens-/, '') : nil
  end
end
