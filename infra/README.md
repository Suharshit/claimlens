# ClaimLens — DevOps pipeline (INT333)

**CI → Release → Terraform → Ansible → Puppet → Nagios**, built from
[`DEVOPS_PIPELINE_TEMPLATE.md`](../DEVOPS_PIPELINE_TEMPLATE.md). Every owner decision is in
[`pipeline.config.yml`](../pipeline.config.yml). This is separate from the CSE476 feature work: it deploys
whatever `main` contains, through the small server mode in [`api.py`](../api.py).

> Educational prototype — not insurance, legal or medical advice.

| Stage | Where | What it does |
| --- | --- | --- |
| S1 App readiness | `api.py` | `GET /healthz`, `GET /version`, `POST /claims/{id}/run` (501 until M7); `PORT`/`HOST`/`APP_VERSION` from env |
| S3 CI | `.github/workflows/ci.yml` | ruff + pytest on 3.11/3.12; lean server install + Nagios plugin smoke test; Terraform/Ansible/Puppet lint |
| S4 Release | `.github/workflows/release.yml` | tag `v*` → GitHub Release with `claimlens.tar.gz` + `.sha256` |
| S5 Infra | `infra/terraform/` | AWS ap-south-1: `lb-1`, `app-1`, `app-2` (t3.micro), `ops-1` (t3.small); writes the Ansible inventory |
| S6 Ansible | `infra/ansible/` | `site.yml` builds everything; `deploy.yml` rolls a new tag out one server at a time |
| S7 Puppet | `infra/puppet/` | OpenVox 8; keeps the service running, owns the nginx LB config, motd, tmp cleanup cron |
| S8 Nagios | `infra/nagios/`, `roles/nagios` | ping, SSH, disk, load, process, `/healthz`, LB, Puppet port; custom `check_app.py` |
| S10 Make | `Makefile` | one command per step (`make help`) |

```text
            Internet :80
                 │
           lb-1 (nginx, Puppet-managed)
           ┌─────┴─────┐  :8000 VPC only
        app-1        app-2     claimlens API + NRPE + Puppet agent
           └─────┬─────┘  :5666 NRPE, :8140 Puppet (VPC only)
               ops-1           Puppet server + Nagios (UI via SSH tunnel)
```

## One-time setup (WSL Ubuntu)

Ansible has no Windows control node, so run all `make` targets from WSL (`Ubuntu-22.04`):

```bash
sudo apt update && sudo apt install -y make rsync unzip pipx git
pipx install --include-deps ansible && pipx inject ansible ansible-lint
# Terraform: https://developer.hashicorp.com/terraform/install (HashiCorp apt repo)
# AWS CLI v2: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
aws configure                          # IAM user with EC2 + VPC rights only, never root keys
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519   # keep the key in WSL's ~/.ssh, not on /mnt
cd /mnt/e/claimlens
```

## First build

```bash
# 1. A release must exist before servers can install it (S4)
make release VERSION=v0.1.0            # after the pipeline branch is merged to main

# 2. Servers (S5): set your IP first
cp infra/terraform/example.tfvars infra/terraform/terraform.tfvars
echo "admin_cidr = \"$(curl -s https://checkip.amazonaws.com)/32\"" >> infra/terraform/terraform.tfvars   # then delete the example line
make infra ENV=dev
make plan                              # ✅ "No changes"

# 3. Configure + deploy (S6)
make configure VERSION=v0.1.0          # ✅ failed=0; run again → mostly changed=0

# 4. Puppet certificate exchange (S7, manual signing)
ssh ubuntu@<ops-ip> 'sudo /opt/puppetlabs/bin/puppetserver ca list'
ssh ubuntu@<ops-ip> 'sudo /opt/puppetlabs/bin/puppetserver ca sign --all'
make puppet-run                        # ✅ agents apply the catalog; lb-1 now serves the site

# 5. Nagios (S8)
make status                            # prints site_url and the nagios_tunnel command
ssh -L 8090:localhost:80 ubuntu@<ops-ip>   # then open http://localhost:8090/nagios4
```

The LB only serves the site after step 4, because Puppet owns its nginx config (`config_owner: puppet`).

## Day to day

| Task | Command |
| --- | --- |
| New version | merge to `main` → `make release VERSION=v0.2.0` → `make deploy VERSION=v0.2.0` |
| Changed Puppet code | `make puppet-code && make puppet-run` |
| Dry run of Ansible | `cd infra/ansible && ansible-playbook site.yml -e app_version=v0.2.0 --check --diff` |
| Test without a release | `make build`, set `app_install_method: copy`, deploy a new version name |

## Demo runbook (S11, about 10 minutes, build everything before)

| # | Show | Command / action | What to say |
| --- | --- | --- | --- |
| 1 | The app | `curl http://<lb>/version`, `curl http://<lb>/healthz` (scenario run once M7 works) | "This is the product." |
| 2 | CI | push a small change, open Actions | "Every push is tested, including the infra code." |
| 3 | Release | `make release VERSION=v1.1.0`, open Releases | "A tag produces a versioned, checksummed artifact." |
| 4 | IaC | `make plan` → *No changes* | "The servers are code; idempotent." |
| 5 | Rolling deploy | `make deploy VERSION=v1.1.0` beside `while true; do curl -s -o /dev/null -w "%{http_code}\n" http://<lb>/healthz; sleep 1; done` | "One server at a time, no downtime; Nagios downtime set automatically." |
| 6 | Nagios | dashboard all green | "Health, disk, load, process and the real feature check." |
| 7 | Break it | `ssh ubuntu@<app-1> sudo systemctl stop claimlens` | "Soft critical, then hard critical; the LB still serves from app-2." |
| 8 | Self-heal | `make puppet-run` | "Puppet pulls the desired state and starts the service again." |
| 9 | Green again | refresh Nagios | "Detected, healed, verified." |
| 10 | Config drift | edit `/etc/nginx/sites-available/default` on lb-1, `make puppet-run` | "Manual edits are reverted; code is the source of truth." |
| 11 | Teardown | `make down` | "Gone, and `make up` brings it back identically." |

## Teardown (always — AWS bills by the hour)

- [ ] `make down` → *Destroy complete!* (repeat with `ENV=prod` if used)
- [ ] AWS console → EC2 (ap-south-1): no instances, volumes or Elastic IPs left

## Security (S9)

- No secrets in git: `terraform.tfvars`, state, `hosts.ini`, `*.pem`, `.env`, `.vault_pass*` are git-ignored.
- SSH and the Nagios UI are reachable only from `admin_cidr` (Terraform rejects `0.0.0.0/0`); app, NRPE and Puppet ports are VPC-only; only the LB is public.
- The app runs as its own `claimlens` user, read-only release folders, `ProtectSystem=strict`; it writes only `/var/lib/claimlens`.
- Puppet autosign is off; certificates are signed by hand.
- Model API key (once the lane is chosen): `ansible-vault create infra/ansible/group_vars/vault.yml`, template it to `/etc/claimlens/env` (the unit already reads it), run with `--ask-vault-pass`.
- Nagios web login is off by default — acceptable only behind the SSH tunnel (see template S8 to turn it on).

## Known limits

- Servers install `requirements-server.txt` (no PyTorch/Chroma): fine for today's stubs; revisit when M3 retrieval lands.
- The Nagios real-function check (scenario 1) is written but switched off until M7 — uncomment `nagios_functional_args` in `group_vars/all.yml`.
- Terraform state is local to your WSL checkout; the S3 backend block in `main.tf` is ready if the project gets a second operator.
