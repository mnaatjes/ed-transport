#!/usr/bin/env bash
# ==============================================================================
# scripts/setup_wine_simulant.sh
#
# Idempotently initializes an isolated Wine prefix and downloads an embeddable
# Windows Python runtime for local cross-platform verification on Linux.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${REPO_ROOT}/.cache"
WINE_PREFIX="${CACHE_DIR}/winepfx"
DOWNLOADS_DIR="${CACHE_DIR}/downloads"
PYTHON_TARGET_DIR="${WINE_PREFIX}/drive_c/Python311"
PYTHON_VERSION="3.11.9"
PYTHON_ZIP="python-${PYTHON_VERSION}-embed-amd64.zip"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_ZIP}"

echo "============================================================"
echo "Initializing Isolated Wine Environment for Windows Testing"
echo "============================================================"

# 1. Pre-flight host binary checks
if ! command -v wine >/dev/null 2>&1; then
    echo "[ERROR] 'wine' is not installed on this host."
    echo "To install on Debian/Ubuntu, run:"
    echo "    sudo apt-get update && sudo apt-get install -y wine64 wine-binfmt"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "[ERROR] 'curl' is required but not installed."
    exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
    echo "[ERROR] 'unzip' is required but not installed."
    exit 1
fi

# 2. Fast-exit if already provisioned
if [[ -f "${PYTHON_TARGET_DIR}/python.exe" ]]; then
    echo "[INFO] Windows Python is already installed at: ${PYTHON_TARGET_DIR}/python.exe"
    echo "[SUCCESS] Wine simulant environment is ready."
    exit 0
fi

# 3. Check if shared wine prefix exists in peer repo (ed-telemetry) to avoid re-download
PEER_CACHE="/home/michael/src/github.com/mnaatjes/ed-telemetry/.cache"
if [[ -d "${PEER_CACHE}/winepfx/drive_c/Python311" ]]; then
    echo "[INFO] Symlinking cached Wine prefix from ed-telemetry peer repository..."
    mkdir -p "${CACHE_DIR}"
    ln -s "${PEER_CACHE}/winepfx" "${WINE_PREFIX}"
    echo "[SUCCESS] Reused existing Wine prefix."
    exit 0
fi

# 4. Initialize isolated Wine prefix
mkdir -p "${DOWNLOADS_DIR}" "${PYTHON_TARGET_DIR}"
export WINEPREFIX="${WINE_PREFIX}"
export WINEDLLOVERRIDES="mscoree,mshtml=" # Suppress Gecko/Mono dialog prompts
export WINEDEBUG="-all"                  # Suppress Wine debug noise

echo "[1/3] Initializing isolated Wine prefix at: ${WINE_PREFIX}..."
wineboot --init >/dev/null 2>&1 || true

# 5. Download embeddable Windows Python
if [[ ! -f "${DOWNLOADS_DIR}/${PYTHON_ZIP}" ]]; then
    echo "[2/3] Downloading Windows embeddable Python ${PYTHON_VERSION}..."
    curl -fsSL "${PYTHON_URL}" -o "${DOWNLOADS_DIR}/${PYTHON_ZIP}"
fi

# 6. Extract into Wine C: drive
echo "[3/3] Extracting Python into Wine C: drive..."
unzip -qo "${DOWNLOADS_DIR}/${PYTHON_ZIP}" -d "${PYTHON_TARGET_DIR}"

# 7. Configure Python ._pth file to include Lib/site-packages
PTH_FILE="${PYTHON_TARGET_DIR}/python311._pth"
if [[ -f "${PTH_FILE}" ]]; then
    sed -i 's/^#import site/import site/' "${PTH_FILE}"
    echo "Lib\\site-packages" >> "${PTH_FILE}"
fi

echo "[SUCCESS] Isolated Wine Windows Python environment ready at ${PYTHON_TARGET_DIR}/python.exe"
