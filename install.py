#!/usr/bin/env python3
"""Install Star Trader into the current user's XDG data directory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def install():
    source = Path(__file__).resolve().parent
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share').expanduser().resolve()
    target = data / 'star-trader'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('star_trader.py', 'save_sync.py', 'update.py', 'LICENSE', 'README.md'):
        destination = target / name
        if (source / name).resolve() != destination.resolve():
            shutil.copy2(source / name, destination)
    from star_trader import VERSION
    (target/'install-info.json').write_text(json.dumps(dict(source=str(source),version=VERSION)),encoding='utf-8')
    apps = data / 'applications'
    apps.mkdir(parents=True, exist_ok=True)
    # Desktop Entry Exec quoting: escape reserved characters, and literal %.
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    launcher = apps / 'star-trader.desktop'
    launcher.write_text('[Desktop Entry]\nType=Application\nName=Star Trader\n'
                        'Comment=Wireframe space trading and combat for Omarchy\n'
                        f'Exec={quote(sys.executable)} {quote(target / "star_trader.py")}\n'
                        'Icon=applications-games\nTerminal=false\nCategories=Game;Simulation;\n'
                        'StartupWMClass=star-trader\n', encoding='utf-8')
    refresh = shutil.which('update-desktop-database')
    if refresh:
        subprocess.run([refresh, str(apps)], check=False)
    print('Installed! Open the Omarchy app launcher and search for Star Trader.')
    print(f'Or run: python3 "{target / "star_trader.py"}"')
    print('Your saved game is preserved when reinstalling.')
    print(f'For future updates: python3 "{target / "update.py"}"')


if __name__ == '__main__':
    install()
