#!/usr/bin/env bash
set -euo pipefail

seed="$(openssl rand -base64 384 | LC_ALL=C tr -dc 'A-Za-z0-9')"
if [ "${#seed}" -lt 256 ]; then
  printf '%s\n' 'Failed to generate a sufficiently long seed.' >&2
  exit 1
fi
printf '%.256s\n' "$seed"
