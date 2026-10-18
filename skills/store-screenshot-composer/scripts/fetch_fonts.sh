#!/bin/bash
#
# Downloads Noto Sans JP (the typeface touyou.dev uses) into the folder compose.py looks in.
# It is a variable font: one file covers both the 700 headline and the 400 supporting text.
#
#   ./fetch_fonts.sh

set -euo pipefail

DEST="${HOME}/.cache/store-screenshot-composer"
FILE="NotoSansJP[wght].ttf"
URL="https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"

mkdir -p "$DEST"
if [ -s "$DEST/$FILE" ]; then
  echo "already there: $DEST/$FILE"
  exit 0
fi
curl -fsSL -o "$DEST/$FILE.part" "$URL"
mv "$DEST/$FILE.part" "$DEST/$FILE"
echo "saved: $DEST/$FILE"
