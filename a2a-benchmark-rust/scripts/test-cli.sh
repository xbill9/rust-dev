#!/bin/bash
# Talk to both agents with the a2a CLI and check the replies.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v a2a >/dev/null || { echo "a2a CLI not on PATH (see README)"; exit 1; }
scripts/start-all.sh
fail=0
check() { # name url
  echo "== $1 ($2)"
  a2a card get -a "$2"
  out=$(a2a send -a "$2" "Calculate the first 5 Mersenne primes")
  echo "$out"
  if grep -q "Found first 5 Mersenne primes" <<<"$out"; then echo "✅ send"; else echo "❌ send"; fail=1; fi
  sout=$(a2a send -a "$2" --stream "first 8")
  if grep -q "Found first 8 Mersenne primes" <<<"$sout"; then echo "✅ stream"; else echo "❌ stream"; echo "$sout"; fail=1; fi
}
check native http://localhost:8104
check exec   http://localhost:8105
# Native agent: both transports, and a data part carrying the count.
for t in jsonrpc rest; do
  o=$(a2a send -a http://localhost:8104 --transport "$t" "first 4")
  grep -q "Found first 4" <<<"$o" && echo "✅ native $t" || { echo "❌ native $t"; fail=1; }
done
o=$(a2a send -a http://localhost:8104 --data-part '{"count": 6}')
grep -q "Found first 6" <<<"$o" && echo "✅ native data-part" || { echo "❌ native data-part"; echo "$o"; fail=1; }
exit $fail
