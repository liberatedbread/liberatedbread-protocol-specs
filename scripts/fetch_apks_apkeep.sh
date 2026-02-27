#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGETS_CSV="${TARGETS_CSV:-$ROOT_DIR/targets/targets.csv}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/workspace/apks/apkeep}"

# apkeep defaults to APKPure per its README; keep that as the default to reduce friction.
APKEEP_SOURCE="${APKEEP_SOURCE:-apk-pure}"

# Keep parallelism low to avoid hammering distributors.
PARALLEL_JOBS="${PARALLEL_JOBS:-2}"

mkdir -p "$OUT_DIR"

if ! command -v apkeep >/dev/null 2>&1; then
  echo "ERROR: apkeep not found. Install from https://github.com/EFForg/apkeep"
  exit 1
fi

if [[ ! -f "$TARGETS_CSV" ]]; then
  echo "ERROR: targets.csv not found at: $TARGETS_CSV"
  exit 1
fi

mapfile -t PKGS < <(awk -F, 'NR>1 && $1!="" {print $1}' "$TARGETS_CSV" | sort -u)

COMMON_ARGS=()
if [[ "$APKEEP_SOURCE" == "google-play" ]]; then
  : "${APKEEP_EMAIL:?Set APKEEP_EMAIL for -d google-play}"
  : "${APKEEP_AAS_TOKEN:?Set APKEEP_AAS_TOKEN for -d google-play}"
  COMMON_ARGS=(-d google-play -e "$APKEEP_EMAIL" -t "$APKEEP_AAS_TOKEN")
else
  COMMON_ARGS=(-d "$APKEEP_SOURCE")
fi

download_one() {
  local pkg="$1"
  echo "[apkeep] downloading: $pkg (source=$APKEEP_SOURCE)"
  # apkeep writes into OUT_DIR; filenames vary by source/version.
  apkeep -a "$pkg" "${COMMON_ARGS[@]}" "$OUT_DIR" || {
    echo "[apkeep] WARN: failed to download $pkg (continuing)"
    return 0
  }
}

export -f download_one
export OUT_DIR APKEEP_SOURCE
export COMMON_ARGS

if command -v parallel >/dev/null 2>&1; then
  printf "%s\n" "${PKGS[@]}" | parallel -j "$PARALLEL_JOBS" download_one {}
else
  for pkg in "${PKGS[@]}"; do
    download_one "$pkg"
  done
fi

# Write a local checksum manifest (kept in workspace/)
if command -v sha256sum >/dev/null 2>&1; then
  find "$OUT_DIR" -maxdepth 1 -type f \( -name "*.apk" -o -name "*.apks" -o -name "*.xapk" \) -print0 \
    | sort -z \
    | xargs -0 sha256sum > "$OUT_DIR/SHA256SUMS.txt" || true
fi

echo "[apkeep] done. Output dir: $OUT_DIR"
