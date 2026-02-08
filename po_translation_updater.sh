#!/usr/bin/env bash

set -e

# ==================================================
# Luanti xgettext helper script
# - CC0, entirely vibecoded
# - Extracts translations only from .lua files
# - Ignores the .git directory
# - Pulls comments with S-NOTE into .pot, stripping prefix
# - Updates .po files safely preserving translations/comments
# ==================================================

LOCALE_DIR="locale"
POT_FILE="$LOCALE_DIR/template.pot"

echo "==> Extracting Lua strings (Luanti)"

# Find all .lua files, excluding .git
FILES=$(find . \
  -path "./.git/*" -prune -o \
  -type f -name "*.lua" -print)

if [ -z "$FILES" ]; then
  echo "No .lua files found"
  exit 0
fi

# Run xgettext with S-NOTE comments
xgettext \
  --language=Lua \
  --from-code=UTF-8 \
  --add-comments=S-NOTE \
  --keyword=S \
  --keyword=PS:1,2 \
  --keyword=NS \
  --keyword=FS \
  --keyword=FPS:1,2 \
  --keyword=NFS \
  --output="$POT_FILE" \
  $FILES

echo "==> POT file generated"

# --------------------------------------------------
# Strip S-NOTE prefix from comments in .pot
# --------------------------------------------------
# Convert:
#   #. S-NOTE: text   -> #. text
#   #  S-NOTE: text   -> # text
#   #: S-NOTE: text   -> #: text
sed -i.bak -E '
  s/^#\. S-NOTE: /#./;
  s/^# S-NOTE: /#/;
  s/^#: S-NOTE: /#:/;
' "$POT_FILE"
rm -f "$POT_FILE.bak"

echo "==> S-NOTE prefix stripped in $POT_FILE"

# --------------------------------------------------
# Update existing .po files using the new POT
# --------------------------------------------------

if [ -d "$LOCALE_DIR" ]; then
  PO_FILES_FOUND=false
  for PO in "$LOCALE_DIR"/*.po; do
    [ -f "$PO" ] || continue
    PO_FILES_FOUND=true
    echo "==> Updating $(basename "$PO")"

    msgmerge --update --backup=none "$PO" "$POT_FILE"
  done

  if ! $PO_FILES_FOUND; then
    echo "No .po files found in $LOCALE_DIR"
  fi
fi

echo "==> Done"

