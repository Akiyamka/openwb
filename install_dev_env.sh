#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR"

export UV_CACHE_DIR="${UV_CACHE_DIR:-$SCRIPT_DIR/.uv-cache}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$SCRIPT_DIR/.uv-python}"

if ! command -v cc >/dev/null 2>&1 && ! command -v gcc >/dev/null 2>&1; then
  cat <<'EOF'
Missing C compiler/build tools.

Home Assistant depends on packages with C extensions, so some dependencies may
need to be compiled during installation. Install compiler tools for your OS:

  Ubuntu/Debian:
    sudo apt update
    sudo apt install build-essential

  Fedora/RHEL:
    sudo dnf install gcc glibc-devel redhat-rpm-config

Then rerun this script.
EOF
  exit 1
fi

PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
PYTHON_BIN="python$PYTHON_VERSION"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  uv python install "$PYTHON_VERSION"
  PYTHON_BIN="$(uv python find "$PYTHON_VERSION")"
fi

uv venv --python "$PYTHON_BIN" --clear
source .venv/bin/activate

uv pip install homeassistant pymodbus==3.11.2 pyserial==3.5 pytest basedpyright
