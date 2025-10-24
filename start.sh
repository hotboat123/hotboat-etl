#!/usr/bin/env bash
set -euo pipefail

# Ensure working dir is repo root
cd "$(dirname "$0")"

python -m jobs.runner


