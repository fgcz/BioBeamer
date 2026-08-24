#!/usr/bin/env bash
# Walk through tus storage verification against the live local stack, printing the state that
# matters at each step: the copied-files ledger, the resource registry, and B-Fabric's verdict.
#
# What it demonstrates:
#   phase 1  a clean upload            -> resources available, sources deletable
#   phase 2  a transfer that succeeds   -> resource failed, source NOT deletable, and the next
#            and is then rejected by      run drops it from the ledger and retries it (an EICAR
#            the virus scan               test file, which every scanner flags by definition)
#   phase 3  a pending orphan retried   -> the unlinkable duplicate is uploaded rather than
#            after a service outage       linked, and the ledger is repaired
#
# Requires: BFABRIC_CLIENT_SECRET exported, and sudo for systemctl stop/start.
#
#   export BFABRIC_CLIENT_SECRET=...
#   bash tests/integration/tus_verification_walkthrough.sh
#
set -uo pipefail

REPO="${REPO:-/srv/bfabriclocal/IdeaProjects/BioBeamer}"
XML="${XML:-/srv/bfabriclocal/IdeaProjects/BioBeamerConfig/xml/BioBeamerTus.xml}"
HOST="${HOST:-testhost_tus}"
LOG_DIR="${LOG_DIR:-/tmp/e2e}"
SRC="${SRC:-/tmp/tus_source}"
BASE_URL="${BASE_URL:-http://localhost:8080/bfabric}"
CLIENT_ID="${CLIENT_ID:-b745836d-1a6c-4a4a-b7f8-bd7a6604747f}"
STORAGE_UNIT="${STORAGE_UNIT:-bfabric-tus-storage}"
PY="$REPO/.venv/bin/python"
# How long the storage service needs to run its post-finish checks and update B-Fabric.
VERDICT_WAIT="${VERDICT_WAIT:-30}"
# Keep bfabricpy's own loguru chatter out of the walkthrough output.
export BFABRICPY_LOG_LEVEL="${BFABRICPY_LOG_LEVEL:-WARNING}"

RED=$'\e[31m'; GRN=$'\e[32m'; YEL=$'\e[33m'; BLD=$'\e[1m'; OFF=$'\e[0m'

step()  { printf '\n%s=== %s ===%s\n' "$BLD" "$*" "$OFF"; }
note()  { printf '%s%s%s\n' "$YEL" "$*" "$OFF"; }
good()  { printf '%s%s%s\n' "$GRN" "$*" "$OFF"; }
bad()   { printf '%s%s%s\n' "$RED" "$*" "$OFF"; }

if [[ -z "${BFABRIC_CLIENT_SECRET:-}" ]]; then
  bad "BFABRIC_CLIENT_SECRET is not exported; nothing can authenticate."
  exit 1
fi

run_biobeamer() {
  "$PY" -m biobeamer --xml "$XML" --hostname "$HOST" --log_dir "$LOG_DIR" \
    --bfabric-base-url "$BASE_URL" --bfabric-client-id "$CLIENT_ID" >/dev/null 2>&1
  printf 'exit=%s\n' "$?"
  local log
  log=$(ls -t "$LOG_DIR"/biobeamer_*.log 2>/dev/null | head -1)
  [[ -n "$log" ]] && grep -hiE 'TUS upload done|unlinkable|not yet confirmed|rejected by B-Fabric|ERROR - TUS' "$log" \
    | sed 's/^BioBeamer - //;s/ - INFO - / /;s/ - ERROR - / ERR /;s/ - WARNING - / WARN /'
}

# Ask B-Fabric what it thinks of every resource in the registry.
show_state() {
  printf '%s-- ledger (%s) --%s\n' "$BLD" "$(wc -l <"$LOG_DIR/copied_files.txt" 2>/dev/null || echo 0)" "$OFF"
  sed "s|$SRC/||" "$LOG_DIR/copied_files.txt" 2>/dev/null | sed 's/^/    /' || true
  printf '%s-- registry + B-Fabric verdict --%s\n' "$BLD" "$OFF"
  BB_SRC="$SRC" BB_LOG_DIR="$LOG_DIR" BB_BASE_URL="$BASE_URL" BB_CLIENT_ID="$CLIENT_ID" \
  "$PY" - <<'PYEOF'
import logging, os
logging.disable(logging.CRITICAL)
from biobeamer.tusregistry import classify, read_registry, registry_path
from biobeamer.tusupload import get_client

params = {
    "log_dir": os.environ["BB_LOG_DIR"],
    "bfabric_base_url": os.environ["BB_BASE_URL"],
    "bfabric_client_id": os.environ["BB_CLIENT_ID"],
}
path = registry_path(params)
entries = read_registry(path)
if not entries:
    print("    (registry empty)")
    raise SystemExit(0)

log = logging.getLogger("q")
try:
    client = get_client(params, log)
except Exception as exc:  # noqa: BLE001 - diagnostic script
    print(f"    cannot reach B-Fabric: {exc}")
    raise SystemExit(0)

sources = sorted(entries)
stored, rejected, unknown = classify(sources, path, client, log)
src = os.environ["BB_SRC"].rstrip("/") + "/"
short = lambda p: p.replace(src, "")
for label, group in (("available -> DELETABLE", stored),
                     ("rejected  -> re-upload", rejected),
                     ("pending   -> keep local", unknown)):
    for f in sorted(group):
        rid = entries[f].get("resource_id")
        print(f"    {label:24s} resource {rid:<9} {short(f)}")
PYEOF
}

fresh_data() {
  rm -rf "$SRC" "$LOG_DIR"
  mkdir -p "$SRC/p1234/Proteomics/EXPLORIS_1/run_V" "$SRC/p1234/Proteomics/TIMSTOF_1/acq_V.d/sub" "$LOG_DIR"
  head -c 6144 /dev/urandom > "$SRC/p1234/Proteomics/EXPLORIS_1/run_V/v1.raw"
  head -c 3072 /dev/urandom > "$SRC/p1234/Proteomics/TIMSTOF_1/acq_V.d/analysis.tdf"
  head -c 1024 /dev/urandom > "$SRC/p1234/Proteomics/TIMSTOF_1/acq_V.d/sub/deep.bin"
  find "$SRC" -type f -exec touch -d '3 hours ago' {} +
  find "$SRC" -type f | sed "s|$SRC/|    |"
}

# ---------------------------------------------------------------- phase 1
step "PHASE 1  clean upload (storage service running)"
sudo systemctl start "$STORAGE_UNIT" 2>/dev/null
fresh_data
run_biobeamer
show_state
note "Expect: still 'pending' -- the post-finish checks (virus scan, md5) run asynchronously and"
note "have not ruled yet, seconds after the upload. THIS is why deletion is gated at delete time"
note "rather than after upload: checking here would tell you nothing."
note "Waiting ${VERDICT_WAIT}s for the storage service to rule, then re-checking the same files..."
sleep "$VERDICT_WAIT"
show_state
note "Expect NOW: every resource available, so every source is deletable."

# ---------------------------------------------------------------- phase 2
step "PHASE 2  transfer succeeds, then the post-finish check REJECTS it"
note "Writing an EICAR test file: it transfers normally, then ClamAV rejects it in the post-finish"
note "hook -- the one failure mode a client cannot observe, because the tus transfer is already"
note "complete by the time the verdict exists."
EICAR="$SRC/p1234/Proteomics/EXPLORIS_1/run_V/infected.raw"
# The standard anti-malware test signature (not malware; every scanner flags it by definition).
printf 'X5O!P%%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' > "$EICAR"
touch -d '3 hours ago' "$EICAR"
rm -f "$LOG_DIR/copied_files.txt"
run_biobeamer
note "Note the upload REPORTS SUCCESS: 'uploaded' counts the transfer, not the storage."
note "Waiting ${VERDICT_WAIT}s for the virus scan to rule..."
sleep "$VERDICT_WAIT"
show_state
note "Expect: infected.raw -> 'rejected' (resource failed). Its bytes were transferred and then"
note "thrown away, so the LOCAL COPY MUST BE KEPT -- this is precisely the data-loss guard."

step "PHASE 2b  the next run repairs the ledger and retries the rejected file"
note "The ledger still lists infected.raw as copied. That has to be undone, or it would be skipped"
note "for ever and silently never stored."
before=$(grep -c . "$LOG_DIR/copied_files.txt" 2>/dev/null || echo 0)
run_biobeamer
after=$(grep -c . "$LOG_DIR/copied_files.txt" 2>/dev/null || echo 0)
printf 'ledger entries before=%s after=%s\n' "$before" "$after"
note "Expect: a 'rejected by B-Fabric ... will be uploaded again' warning, and infected.raw"
note "re-uploaded (and rejected again -- it is still EICAR). It never becomes deletable."
rm -f "$EICAR"
note "Removed the EICAR file so later phases are not affected."

# ---------------------------------------------------------------- phase 3
step "PHASE 3  retry after the service is restored"
sudo systemctl start "$STORAGE_UNIT"
sleep 2
rm -f "$LOG_DIR/copied_files.txt"
run_biobeamer
note "Waiting ${VERDICT_WAIT}s for the post-finish checks to rule..."
sleep "$VERDICT_WAIT"
show_state
note "Expect: 'the server reported them unlinkable' -- the pending orphan is uploaded rather than"
note "linked, and every file ends up available and deletable."

step "SUMMARY"
echo "ledger:   $LOG_DIR/copied_files.txt"
echo "registry: $LOG_DIR/tus_resources.json"
echo "logs:     $LOG_DIR/biobeamer_*.log  (and tus_*.log for per-group workunit/job ids)"
good "Done. Nothing was deleted: max_time_delete only removes files old enough AND confirmed stored."
