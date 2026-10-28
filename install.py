#!/usr/bin/env python3
"""Install Star Trader into the current user's XDG data directory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def install_mac_app(target):
    # A minimal app bundle in ~/Applications, so Star Trader opens from Launchpad, Spotlight or the Dock.
    bundle = Path(os.environ.get('STAR_TRADER_APP') or Path.home()/'Applications'/'Star Trader.app')
    app = bundle/'Contents'
    (app/'MacOS').mkdir(parents=True, exist_ok=True)
    (app/'Info.plist').write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        '<key>CFBundleName</key><string>Star Trader</string>\n'
        '<key>CFBundleIdentifier</key><string>io.github.womb4t.star-trader</string>\n'
        '<key>CFBundleExecutable</key><string>star-trader</string>\n'
        '<key>CFBundlePackageType</key><string>APPL</string>\n'
        '<key>CFBundleIconFile</key><string>StarTrader</string>\n'
        '<key>NSHighResolutionCapable</key><true/>\n'
        '<key>LSMinimumSystemVersion</key><string>10.13</string>\n'
        '</dict></plist>\n', encoding='utf-8')
    def quote(value): return "'" + str(value).replace("'", "'\\''") + "'"
    game = quote(target/'star_trader.py')
    private = app/'Resources'/'python'/'bin'/'python3'
    interpreter = app/'MacOS'/'Star Trader'
    if private.exists():
        # The Dock names an app after the bundle holding the running binary, so run a copy of the
        # app's private (statically linked) Python from Contents/MacOS, pointed at its own library.
        shutil.copy2(private.resolve(), interpreter)
        script = ('#!/bin/sh\n'
                  'contents="$(cd "$(dirname "$0")/.." && pwd)"\n'
                  'export PYTHONHOME="$contents/Resources/python"\n'
                  'export SSL_CERT_FILE="$contents/Resources/cacert.pem"\n'
                  'export STAR_TRADER_FRAMEWORKS="$contents/Frameworks"\n'
                  f'[ -x "$contents/MacOS/Star Trader" ] && exec "$contents/MacOS/Star Trader" {game} "$@"\n'
                  f'exec "$PYTHONHOME/bin/python3" {game} "$@"\n')
    else:
        interpreter.unlink(missing_ok=True)
        script = f'#!/bin/sh\nexec {quote(sys.executable)} {game} "$@"\n'
    launcher = app/'MacOS'/'star-trader'
    launcher.write_text(script, encoding='utf-8')
    launcher.chmod(0o755)
    icon = Path(__file__).resolve().parent/'assets'/'StarTrader.icns'
    if icon.is_file():
        (app/'Resources').mkdir(exist_ok=True)
        shutil.copy2(icon, app/'Resources'/'StarTrader.icns')
    print('Installed! Open Star Trader from Launchpad, Spotlight, or ~/Applications.')
    print('Your saved game is preserved when reinstalling. When a new release is out, the start screen offers to install it.')


def install():
    source = Path(__file__).resolve().parent
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share').expanduser().resolve()
    target = data / 'star-trader'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('star_trader.py', 'startup.py', 'presence.py', 'save_sync.py', 'update.py', 'LICENSE', 'README.md'):
        destination = target / name
        if (source / name).resolve() != destination.resolve():
            shutil.copy2(source / name, destination)
    assets = target/'assets'
    assets.mkdir(exist_ok=True)
    splash = source/'assets/star-trader-splash.bmp.gz'
    if splash.resolve() != (assets/splash.name).resolve():
        shutil.copy2(splash,assets/splash.name)
    icon = source/'assets/star-trader-icon.png'
    if icon.resolve() != (assets/icon.name).resolve():
        shutil.copy2(icon,assets/icon.name)
    from startup import migrate_online_launcher
    migrate_online_launcher(Path.home()/'.local/bin/star-trader-online')
    from star_trader import VERSION
    (target/'install-info.json').write_text(json.dumps(dict(source=str(source),version=VERSION)),encoding='utf-8')
    if sys.platform == 'darwin':
        install_mac_app(target)
        return
    apps = data / 'applications'
    apps.mkdir(parents=True, exist_ok=True)
    # Desktop Entry Exec quoting: escape reserved characters, and literal %.
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    launcher = apps / 'star-trader.desktop'
    launcher.write_text('[Desktop Entry]\nType=Application\nName=Star Trader\n'
                        'Comment=Wireframe space trading and combat for Omarchy\n'
                        f'Exec={quote(sys.executable)} {quote(target / "star_trader.py")}\n'
                        f'Icon={assets / icon.name}\nTerminal=false\nCategories=Game;Simulation;\n'
                        'StartupWMClass=star-trader\n', encoding='utf-8')
    old_online = apps/'star-trader-online.desktop'
    if old_online.exists() and 'star-trader-online' in old_online.read_text():
        old_online.unlink()
    refresh = shutil.which('update-desktop-database')
    if refresh:
        subprocess.run([refresh, str(apps)], check=False)
    print('Installed! Open the Omarchy app launcher and search for Star Trader.')
    print(f'Or run: python3 "{target / "star_trader.py"}"')
    print('Your saved game is preserved when reinstalling.')
    print(f'For future updates: python3 "{target / "update.py"}"')


if __name__ == '__main__':
    install()
