#!/usr/bin/env bash
# Upload spike S3b to Kaggle. The automatic run stops within a minute (no HF secret in CLI runs);
# start the real run from the Kaggle editor with Save Version -> Save & Run All.
set -euo pipefail
cd "$(dirname "$0")"
: "${KAGGLE_USERNAME:?Set KAGGLE_USERNAME to your Kaggle username}"
kaggle() { uvx --python 3.12 --from 'kaggle>=1.8' kaggle "$@"; }
sed "s/KAGGLE_USERNAME/${KAGGLE_USERNAME}/g" kernel-metadata.template.json > kernel-metadata.json
kaggle kernels push -p . --accelerator NvidiaTeslaT4
echo "Uploaded. Open https://www.kaggle.com/code/${KAGGLE_USERNAME}/voxshift-s3b → Edit → attach HF_TOKEN → Save & Run All."
