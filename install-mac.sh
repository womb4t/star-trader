#!/usr/bin/env bash
# Install Star Trader on macOS with nothing extra: no Xcode tools, git, Homebrew or system Python.
#   curl -fsSL https://raw.githubusercontent.com/womb4t/star-trader/main/install-mac.sh | bash
# Everything the game needs (a private Python, SDL2 and SDL2_ttf) goes inside ~/Applications/Star Trader.app.
set -euo pipefail
if [[ "$(uname)" != Darwin ]]; then
  echo 'This installer is for macOS. On Omarchy, run install.sh instead.' >&2
  exit 1
fi

app="$HOME/Applications/Star Trader.app"
contents="$app/Contents"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

download() {  # url, destination, sha256 (empty to skip the check)
  curl -fsSL --retry 3 -o "$2" "$1"
  if [[ -n "$3" ]] && ! echo "$3  $2" | shasum -a 256 -c - >/dev/null; then
    echo "Download did not match its checksum: $1" >&2
    exit 1
  fi
}

# 1. Game files: this checkout when run from one (or STAR_TRADER_SOURCE), otherwise the latest release.
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || true)"
if [[ -n "${STAR_TRADER_SOURCE:-}" ]]; then
  source_dir="$STAR_TRADER_SOURCE"
elif [[ -n "$script_dir" && -f "$script_dir/star_trader.py" && -f "$script_dir/install.py" ]]; then
  source_dir="$script_dir"
else
  tag="$(curl -fsSL https://api.github.com/repos/womb4t/star-trader/releases/latest | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)"
  [[ -n "$tag" ]] || { echo 'Could not find the latest Star Trader release.' >&2; exit 1; }
  echo "Downloading Star Trader $tag..."
  download "https://github.com/womb4t/star-trader/archive/refs/tags/$tag.tar.gz" "$work/game.tar.gz" ''
  tar -xzf "$work/game.tar.gz" -C "$work"
  source_dir="$(find "$work" -maxdepth 1 -type d -name 'star-trader-*' | head -n 1)"
fi

# 2. A private Python (python-build-standalone: statically linked, one build per processor type).
case "$(uname -m)" in
  arm64) runtime=cpython-3.12.15+20261003-aarch64-apple-darwin-install_only.tar.gz
         runtime_sha=316a463172740e71d8dca1f2730784e325f3f720941137b5d674d5801a632213 ;;
  x86_64) runtime=cpython-3.12.15+20261003-x86_64-apple-darwin-install_only.tar.gz
          runtime_sha=a8fd7a91852f19b6d959793ef41fad048631ccb2a334a9ecdf573255298f7978 ;;
  *) echo "Unsupported Mac processor: $(uname -m)" >&2; exit 1 ;;
esac
python_home="$contents/Resources/python"
python="$python_home/bin/python3"
if [[ "$(cat "$python_home/.runtime" 2>/dev/null)" != "$runtime" ]]; then
  echo 'Downloading Python for Star Trader...'
  download "https://github.com/astral-sh/python-build-standalone/releases/download/20261003/${runtime/+/%2B}" "$work/python.tar.gz" "$runtime_sha"
  rm -rf "$python_home"
  mkdir -p "$contents/Resources"
  tar -xzf "$work/python.tar.gz" -C "$contents/Resources"
  echo "$runtime" > "$python_home/.runtime"
fi

# 3. SDL2 and SDL2_ttf: official universal frameworks from libsdl-org, kept inside the app.
install_framework() {
  local name=$1 url=$2 sha256=$3 found
  [[ -d "$contents/Frameworks/$name.framework" ]] && return
  echo "Downloading $name..."
  download "$url" "$work/$name.dmg" "$sha256"
  mkdir -p "$work/$name-mount" "$contents/Frameworks"
  hdiutil attach -nobrowse -readonly -quiet -mountpoint "$work/$name-mount" "$work/$name.dmg"
  found="$(find "$work/$name-mount" -maxdepth 2 -type d -name "$name.framework" | head -n 1)"
  [[ -n "$found" ]] && cp -R "$found" "$contents/Frameworks/"
  hdiutil detach -quiet "$work/$name-mount"
  [[ -n "$found" ]] || { echo "$name.framework was not found in the download." >&2; exit 1; }
}
install_framework SDL2 \
  https://github.com/libsdl-org/SDL/releases/download/release-2.32.10/SDL2-2.32.10.dmg \
  4a7ac31640d70214e848f994be8a12849c0f97918a7e6c2e27a40036166d1a7f
install_framework SDL2_ttf \
  https://github.com/libsdl-org/SDL_ttf/releases/download/release-2.24.0/SDL2_ttf-2.24.0.dmg \
  677404e23a1a5f6efcbe64697471c5161283e4af5a6403dcb92235d7d83805cd

# 4. Trusted certificates for HTTPS (the private Python cannot read the macOS keychain itself).
security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain > "$contents/Resources/cacert.pem"

# 5. App icon from the artwork, using tools built into macOS.
icon_png="$source_dir/assets/star-trader-icon.png"
if [[ -f "$icon_png" ]] && command -v iconutil >/dev/null; then
  iconset="$work/StarTrader.iconset"
  mkdir -p "$iconset"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$icon_png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
    sips -z "$((size * 2))" "$((size * 2))" "$icon_png" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$iconset" -o "$source_dir/assets/StarTrader.icns" || true
fi

# 6. Game files, launcher and app bundle.
STAR_TRADER_APP="$app" "$python" "$source_dir/install.py"

# The Dock names an app after the bundle holding the running binary, so the launcher runs a copy of
# the private Python from Contents/MacOS. Make sure it really starts; otherwise run Python directly.
interpreter="$contents/MacOS/Star Trader"
if ! PYTHONHOME="$python_home" "$interpreter" -c 'import ctypes, json, ssl, sqlite3' >/dev/null 2>&1; then
  rm -f "$interpreter"
  echo 'Note: using the private Python directly, so the Dock may show Python instead of Star Trader.'
fi
# Finder caches app icons; touching the bundle makes it pick up a new one.
touch "$app"
echo 'Star Trader is installed. Open it from Launchpad, Spotlight or ~/Applications.'
