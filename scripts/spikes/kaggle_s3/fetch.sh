#!/usr/bin/env bash
# Show the status of spike S3 on Kaggle and download its output into ./out/.
set -euo pipefail
cd "$(dirname "$0")"
: "${KAGGLE_USERNAME:?Set KAGGLE_USERNAME to your Kaggle username}"
kaggle() { uvx --python 3.12 --from 'kaggle>=1.8' kaggle "$@"; }
kaggle kernels status "${KAGGLE_USERNAME}/voxshift-s3"
mkdir -p out
kaggle kernels output "${KAGGLE_USERNAME}/voxshift-s3" -p out
echo "Results: $(pwd)/out/s3/ (summary.md, review_*.md, audio/, results.json, logs/)"
