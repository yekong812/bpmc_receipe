#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  echo '먼저 README.md의 의존성 설치 단계를 실행해주세요.' >&2
  exit 1
fi
exec .venv/bin/python scripts/dev.py
