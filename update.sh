#!/usr/bin/env bash
# SalmanPDF — update dari GitHub (pola yang sama kayak kyai-update).
# Jalan dari dalam folder clone repo ini:
#   ./update.sh
# Yang dilakukan: git pull --ff-only, lalu dependency di-sync otomatis
# oleh run.sh pada jalan berikutnya (stamp hash requirements.txt).
set -e
cd "$(dirname "$0")"

if [ ! -d .git ]; then
  echo "❌ Folder ini bukan clone git. Update via GitHub hanya untuk"
  echo "   install cara clone:"
  echo "   git clone https://github.com/riccohsaputra/salmanpdf.git"
  exit 1
fi

# File hasil push snapshot GitHub kehilangan bit executable; chmod +x yang
# pernah dilakukan user terbaca git sebagai "local changes" dan MEMBLOKIR
# pull ("would be overwritten by merge" — kejadian 2026-10-25 di laptop
# Ricco). Matikan pelacakan mode file di clone ini supaya itu tidak
# pernah terulang; perubahan ISI file tetap terdeteksi normal.
git config core.fileMode false 2>/dev/null || true

OLD=$(python3 -c "import re;print(re.search(r'__version__ = \"(.+)\"', open('salmanpdf/__init__.py').read()).group(1))" 2>/dev/null || echo "?")
echo "📄 Versi sekarang: $OLD — menarik update…"
git pull --ff-only
NEW=$(python3 -c "import re;print(re.search(r'__version__ = \"(.+)\"', open('salmanpdf/__init__.py').read()).group(1))" 2>/dev/null || echo "?")

if [ "$OLD" = "$NEW" ]; then
  echo "✅ Sudah versi terbaru ($NEW), tidak ada perubahan."
else
  echo "✅ Update beres: $OLD → $NEW"
fi
echo "   Dependency akan di-sync otomatis saat ./run.sh berikutnya."
