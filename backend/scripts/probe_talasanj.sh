#!/usr/bin/env bash
# Run in Termux:  pkg install curl jq
# Your key is typed into the prompt (hidden) and is never printed or saved.
set -euo pipefail
read -rsp "Talasanj API key: " KEY; echo
curl -sS -m 20 -o raw.json -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $KEY" "https://talasanj.info/api/v1/prices"
unset KEY
echo "--- structure (types only) ---"
jq -c 'def shape: if type=="object" then with_entries(.value|=shape) elif type=="array" then (if length>0 then [.[0]|shape] else [] end) else type end; shape' raw.json
echo "--- first 3 items, safe to paste ---"
jq 'if type=="array" then .[0:3] else (to_entries|.[0:3]|from_entries) end' raw.json
grep -qi "bearer\|api[_-]key" raw.json && echo "WARNING: response mentions a key; review before sharing" || true
