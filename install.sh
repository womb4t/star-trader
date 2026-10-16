#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f /etc/arch-release ]] || ! command -v omarchy >/dev/null; then
  echo 'This installer is for Omarchy. See README.md for manual installation.' >&2
  exit 1
fi
missing=()
for package in python sdl2-compat sdl2_ttf ttf-dejavu; do
  if ! pacman -Q "$package" >/dev/null 2>&1; then
    # JetBrains Mono is already included with Omarchy.
    if [[ "$package" == ttf-dejavu && -f /usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf ]]; then
      continue
    fi
    missing+=("$package")
  fi
done
if ((${#missing[@]})); then
  omarchy pkg add "${missing[@]}"
fi
python3 "$source_dir/install.py"
