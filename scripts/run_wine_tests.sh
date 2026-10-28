#!/usr/bin/env bash
# ==============================================================================
# scripts/run_wine_tests.sh
#
# Executes Python cross-platform verification tests inside Wine under Windows NT.
# ==============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${REPO_ROOT}/.cache"
WINE_PREFIX="${CACHE_DIR}/winepfx"
PYTHON_EXE="${WINE_PREFIX}/drive_c/Python311/python.exe"

if [[ ! -f "${PYTHON_EXE}" ]]; then
    # Try setting up or symlinking
    "${REPO_ROOT}/scripts/setup_wine_simulant.sh"
fi

export WINEPREFIX="${WINE_PREFIX}"
export WINEDEBUG="-all"

echo "============================================================"
echo "Running ed-transport Verification under Windows NT via Wine"
echo "============================================================"

WIN_REPO_ROOT="$(wine winepath -w "${REPO_ROOT}")"

wine "${PYTHON_EXE}" -c "
import sys, os, platform
print(f'Platform: {platform.system()} {platform.release()}')
print(f'Python:   {sys.version}')
print(f'Path sep: {os.path.sep}')
"

echo "Checking package source import under Windows NT environment..."
wine "${PYTHON_EXE}" -c "
import sys
sys.path.insert(0, r'${WIN_REPO_ROOT}\src')

import ed_transport
print(f'Successfully imported ed_transport version {ed_transport.__version__} under Windows NT!')
"

echo "All Wine Windows NT simulant checks passed!"
