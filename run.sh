#!/usr/bin/env bash
# Tangerine Linux — launcher untuk Linux Mint (install dari zip).
# venv dibuat sekali; setelah itu dependency di-sync ulang HANYA kalau
# requirements.txt berubah (dijaga pakai stamp hash) — jadi update versi
# baru cukup ekstrak menimpa folder ini, lalu ./run.sh seperti biasa.
set -e
cd "$(dirname "$0")"

for lib in libEGL.so.1 libGL.so.1; do
  if ! ldconfig -p | grep -q "$lib"; then
    echo "⚠️  $lib belum ada. Install dulu:"
    echo "    sudo apt install libegl1 libgl1 libxkbcommon0"
  fi
done

if [ ! -d .venv ]; then
  echo "🍊 Bikin virtual environment…"
  python3 -m venv .venv
fi

REQ_HASH=$(md5sum requirements.txt | cut -d' ' -f1)
STAMP=.venv/.requirements-hash
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$REQ_HASH" ]; then
  echo "🍊 Sync dependency…"
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  echo "$REQ_HASH" > "$STAMP"
  echo "✅ Dependency siap."
fi

exec .venv/bin/python main.py "$@"
