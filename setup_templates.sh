#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

if command -v pwsh >/dev/null 2>&1; then
    exec pwsh -NoProfile -ExecutionPolicy Bypass -File "$script_dir/setup_templates.ps1" "$@"
fi

if command -v powershell.exe >/dev/null 2>&1; then
    exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$script_dir/setup_templates.ps1" "$@"
fi

echo "PowerShell is required to run setup_templates.ps1." >&2
exit 1
