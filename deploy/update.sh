#!/bin/bash
#
# Apply the current checkout to the running service: sync the venv and restart.
#
# Called by r2lab-embedded/services/run-updates.sh after it has moved this
# repo to the latest origin commit; can also be run by hand to force a redeploy.
# The git update itself is NOT done here, since resetting a repo under a
# running script is unsafe.
#

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")/.."

export PATH="/root/.local/bin:$PATH"

uv sync --frozen
systemctl daemon-reload
systemctl restart r2lab-sidecar
