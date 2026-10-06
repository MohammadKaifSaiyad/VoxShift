#!/usr/bin/env bash
# Push spike S1 to Kaggle and start it on a T4 GPU.
# Needs: a Kaggle API token in ~/.kaggle/access_token, and KAGGLE_USERNAME set.
# Kaggle CLI >= 1.8 reads access_token; it needs Python >= 3.10, hence --python 3.12.
set -euo pipefail
cd "$(dirname "$0")"
: "${KAGGLE_USERNAME:?Set KAGGLE_USERNAME to your Kaggle username}"
kaggle() { uvx --python 3.12 --from 'kaggle>=1.8' kaggle "$@"; }
sed "s/KAGGLE_USERNAME/${KAGGLE_USERNAME}/" kernel-metadata.template.json > kernel-metadata.json
kaggle kernels push -p . --accelerator NvidiaTeslaT4
echo "Started. Check with: scripts/spikes/kaggle_s1/fetch.sh"
