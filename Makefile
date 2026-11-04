# ClaimLens DevOps pipeline (DEVOPS_PIPELINE_TEMPLATE.md, S10). Run from WSL or Linux.
TF      := infra/terraform
ANS     := infra/ansible
ENV     ?= dev
VERSION ?= $(shell git describe --tags --abbrev=0 2>/dev/null || echo v0.0.0)

# Under WSL the repo sits on /mnt/<drive>, which is world-writable, so Ansible
# ignores ansible.cfg there unless it is named explicitly.
export ANSIBLE_CONFIG := $(CURDIR)/$(ANS)/ansible.cfg

.PHONY: help lint test build release infra plan collections configure deploy puppet-code puppet-run status up down

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

lint:            ## lint the app
	ruff check .

test:            ## run app tests
	pytest

build:           ## build dist/claimlens.tar.gz from the committed HEAD
	mkdir -p dist
	git archive --format=tar.gz -o dist/claimlens.tar.gz HEAD

release:         ## tag and push a release (make release VERSION=v1.2.0)
	git tag $(VERSION) && git push origin $(VERSION)

infra:           ## create servers with Terraform (ENV=dev|prod workspace)
	cd $(TF) && terraform init -input=false && terraform workspace select -or-create $(ENV) && terraform apply -auto-approve

plan:            ## terraform plan; right after apply it must say "No changes"
	cd $(TF) && terraform workspace select $(ENV) && terraform plan

collections:     ## install the Ansible collections
	cd $(ANS) && ansible-galaxy collection install -r requirements.yml

configure: collections  ## install everything with Ansible
	cd $(ANS) && ansible-playbook site.yml -e app_version=$(VERSION)

deploy:          ## rolling deploy of VERSION
	cd $(ANS) && ansible-playbook deploy.yml -e app_version=$(VERSION)

puppet-code:     ## ship changed Puppet code to the Puppet server
	cd $(ANS) && ansible-playbook site.yml --tags puppet_code -e app_version=$(VERSION)

puppet-run:      ## run Puppet on every agent now
	cd $(ANS) && ansible 'app:lb' -b -m ansible.builtin.command -a '/opt/puppetlabs/bin/puppet agent -t' || true

status:          ## show what is running
	cd $(TF) && terraform output
	cd $(ANS) && ansible app -b -m ansible.builtin.command -a 'systemctl is-active claimlens'

up: infra configure   ## everything from zero

down:            ## destroy all cloud resources
	cd $(TF) && terraform destroy
