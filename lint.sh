#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -d .venv ]]; then
  cat <<'EOF'
Missing .venv.

Run ./install_dev_env.sh before linting.
EOF
  exit 1
fi

if [[ -x .venv/bin/basedpyright ]]; then
  exec .venv/bin/basedpyright --level error "$@"
fi

if command -v basedpyright >/dev/null 2>&1; then
  exec basedpyright --level error "$@"
fi

cat <<'EOF'
Missing basedpyright.

Run ./install_dev_env.sh to install the development dependencies.
EOF
exit 1
