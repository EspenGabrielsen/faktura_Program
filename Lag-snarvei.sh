#!/bin/sh
# Kjør denne filen fra programmappen for å lage en snarvei på skrivebordet.
set -eu
program_folder=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
desktop_folder=$(xdg-user-dir DESKTOP)
mkdir -p "$desktop_folder"
chmod +x "$program_folder/Gardsfaktura"

# Desktop-filer trenger anførselstegn rundt programstier som inneholder mellomrom.
quoted_program=$(printf '%s' "$program_folder/Gardsfaktura" | sed 's/\\/\\\\/g; s/"/\\"/g; s/`/\\`/g; s/\$/\\$/g; s/%/%%/g')
shortcut="$desktop_folder/Gardsfaktura.desktop"
cat > "$shortcut" <<EOF
[Desktop Entry]
Type=Application
Name=Gårdsfaktura
Comment=Offline fakturering for gården
Exec="$quoted_program"
Icon=accessories-calculator
Terminal=false
Categories=Office;
EOF
chmod +x "$shortcut"
if command -v gio >/dev/null 2>&1; then
    gio set "$shortcut" metadata::trusted true 2>/dev/null || true
fi
printf 'Snarvei opprettet: %s\n' "$shortcut"
