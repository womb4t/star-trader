#!/usr/bin/env bash
# Install Star Trader on macOS: the SDL2 frameworks it needs, then the game and a launcher app.
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname)" != Darwin ]]; then
  echo 'This installer is for macOS. On Omarchy, run install.sh instead.' >&2
  exit 1
fi

python=''
for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    python="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$python" ]]; then
  echo 'Python 3.9 or later is required: https://www.python.org/downloads/macos/ then run this again.' >&2
  exit 1
fi

# Official universal (Intel and Apple Silicon) builds from libsdl-org; Homebrew no longer builds these on Intel Macs.
frameworks="$HOME/Library/Frameworks"
install_framework() {
  local name=$1 url=$2 sha256=$3 work found
  if [[ -d "$frameworks/$name.framework" ]]; then
    echo "$name is already installed."
    return
  fi
  echo "Downloading $name..."
  work="$(mktemp -d)"
  curl -fsSL -o "$work/$name.dmg" "$url"
  if ! echo "$sha256  $work/$name.dmg" | shasum -a 256 -c - >/dev/null; then
    rm -rf "$work"
    echo "$name download did not match its checksum; nothing was installed." >&2
    exit 1
  fi
  mkdir "$work/mount"
  hdiutil attach -nobrowse -readonly -quiet -mountpoint "$work/mount" "$work/$name.dmg"
  found="$(find "$work/mount" -maxdepth 2 -type d -name "$name.framework" | head -n 1)"
  if [[ -n "$found" ]]; then
    mkdir -p "$frameworks"
    cp -R "$found" "$frameworks/"
  fi
  hdiutil detach -quiet "$work/mount"
  rm -rf "$work"
  if [[ -z "$found" ]]; then
    echo "$name.framework was not found in the download." >&2
    exit 1
  fi
  echo "$name installed in $frameworks."
}
install_framework SDL2 \
  https://github.com/libsdl-org/SDL/releases/download/release-2.32.10/SDL2-2.32.10.dmg \
  4a7ac31640d70214e848f994be8a12849c0f97918a7e6c2e27a40036166d1a7f
install_framework SDL2_ttf \
  https://github.com/libsdl-org/SDL_ttf/releases/download/release-2.24.0/SDL2_ttf-2.24.0.dmg \
  677404e23a1a5f6efcbe64697471c5161283e4af5a6403dcb92235d7d83805cd

# Build the app icon from the 1024x1024 artwork, if provided.
icon_png="$source_dir/assets/star-trader-icon.png"
if [[ -f "$icon_png" ]]; then
  iconset="$(mktemp -d)/StarTrader.iconset"
  mkdir "$iconset"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$icon_png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
    sips -z "$((size * 2))" "$((size * 2))" "$icon_png" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$iconset" -o "$source_dir/assets/StarTrader.icns"
  rm -rf "$(dirname "$iconset")"
fi

"$python" "$source_dir/install.py"
app="$HOME/Applications/Star Trader.app"
interpreter="$app/Contents/MacOS/Star Trader"
game="${XDG_DATA_HOME:-$HOME/.local/share}/star-trader/star_trader.py"
works=1
if [[ -f "$interpreter" ]]; then
  # The bundle holds a copy of Python's app binary. Some Pythons (Apple's Command Line Tools)
  # find their library relative to where that binary lives; point those links at the real files.
  original="$("$python" -c 'import sys, pathlib; print(pathlib.Path(sys.base_prefix)/"Resources/Python.app/Contents/MacOS/Python")')"
  while read -r dependency; do
    relative="${dependency#@executable_path/}"
    relative="${relative#@loader_path/}"
    target="$("$python" -c 'import os, sys; print(os.path.realpath(os.path.join(os.path.dirname(sys.argv[1]), sys.argv[2])))' "$original" "$relative")"
    install_name_tool -change "$dependency" "$target" "$interpreter" 2>/dev/null || works=0
  done < <(otool -L "$interpreter" | awk 'NR > 1 && ($1 ~ /^@executable_path\// || $1 ~ /^@loader_path\//) {print $1}')
  # Its original signature binds Python.app's Info.plist, so macOS would kill it here:
  # re-sign it ad hoc first, then the bundle around it.
  codesign --force --sign - "$interpreter" >/dev/null 2>&1 || works=0
  codesign --force --sign - "$app" >/dev/null 2>&1 || works=0
  codesign --verify --deep --strict "$app" >/dev/null 2>&1 || works=0
  # Signing can pass while the binary still cannot start, so check it really runs.
  ((works)) && "$interpreter" -c 'import ctypes, json, ssl' >/dev/null 2>&1 || works=0
fi
if [[ -f "$interpreter" ]] && ((works)); then
  echo 'App bundle signed and checked.'
else
  # Fall back to running Python directly: the Dock then shows Python, but the game opens.
  rm -f "$interpreter"
  printf '#!/bin/sh\nexec "%s" "%s" "$@"\n' "$python" "$game" > "$app/Contents/MacOS/star-trader"
  chmod 755 "$app/Contents/MacOS/star-trader"
  codesign --force --sign - "$app" >/dev/null 2>&1 || true
  echo 'Note: using Python directly, so the Dock may show Python instead of Star Trader.'
fi
# Finder caches app icons; touching the bundle makes it pick up a new one.
touch "$app"
