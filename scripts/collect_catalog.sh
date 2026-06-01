#!/usr/bin/env bash
set -euo pipefail

host="${1:-woodstock}"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${repo_dir}/public/catalog.json"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

ssh "$host" 'python3 -' < "${repo_dir}/scripts/woodstock_inventory.py" > "$tmp"
python3 -m json.tool "$tmp" > /dev/null
mv "$tmp" "$out"

python3 - "$out" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
summary = data["summary"]
print(f"Wrote {sys.argv[1]}")
print(f"Total entries: {summary['total']}")
for source, count in summary["bySource"].items():
    print(f"{source}: {count}")
PY
