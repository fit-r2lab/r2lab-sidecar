help:
	@echo "make preplab to push on V0"
	@echo "make r2lab to push on production"

############################## for deploying before packaging
# default is to mess with our preplab and let the production
# site do proper upgrades using pip3
deployment ?= preplab

ifeq "$(deployment)" "production"
    DEST=r2lab.inria.fr
else
    DEST=preplab.pl.sophia.inria.fr
endif

TMPDIR=/tmp/r2lab-dev-sidecar
# installing in $(TMPDIR) for testing
sync:
	@echo '===== '
	rsync -ai --relative $$(git ls-files) root@$(DEST):$(TMPDIR)
	@echo '===== once copied, do the following as root on $(DEST)'
	@echo 'conda activate r2lab-dev-xxx && pip install -e $(TMPDIR)'

r2lab:
	$(MAKE) sync deployment=production

preplab:
	$(MAKE) sync deployment=preplab

.PHONY: sync r2lab preplab

########## actually install
infra:
	apssh -t r2lab.infra pip3 install --upgrade r2lab-sidecar
	ssh root@faraday.inria.fr systemctl restart r2lab-sidecar

check:
	apssh -t r2lab.infra r2lab-sidecar --version

.PHONY: infra check
