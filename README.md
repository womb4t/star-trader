# Star Trader

A compact, original Elite-inspired space trading game written in Python. Fly a wireframe spaceship, trade across eight star systems, fight pirates, and dock to save your progress.

## Install on Omarchy

Open a terminal and run:

```bash
git clone https://github.com/womb4t/star-trader.git
cd star-trader
bash install.sh
```

The installer uses `omarchy pkg add` only for missing dependencies (Python, SDL2 compatibility libraries, SDL2_ttf, and a font). If needed, Omarchy asks for your password in the terminal. The game itself installs for your user, without sudo.

Open the Omarchy application launcher and search for **Star Trader**.

To update, run `git pull` and `bash install.sh` again from this checkout. Your saved game is preserved.

## Omarchy desktop support

The native SDL window works with Hyprland, can be resized or tiled, and scales its cockpit to fit. Press **F11** to toggle fullscreen. Switching focus releases held controls. No compositor configuration changes are needed.

Game files install under `${XDG_DATA_HOME:-~/.local/share}/star-trader/`; the launcher is under the same data directory in `applications/star-trader.desktop`. The save is `star-trader/save.json`. Existing default-location saves continue to work unless you change XDG_DATA_HOME.

To remove the launcher and installed code while keeping your save:

```bash
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -f "$data_dir/applications/star-trader.desktop"
rm -f "$data_dir/star-trader/star_trader.py" "$data_dir/star-trader/README.md" "$data_dir/star-trader/LICENSE"
```

## Run without installing

```bash
python3 star_trader.py
```

Requires Python 3, SDL2/SDL2-compat, SDL2_ttf, and JetBrains Mono Nerd Font or DejaVu Sans Mono. No pip packages or network connection are needed to play.

## Controls

| Location | Controls |
| --- | --- |
| Station | Up/Down select goods, B buy, S sell, R refuel and repair, L launch |
| Flight | Arrows steer, W accelerate, S brake, Space fire, D dock |
| Galaxy chart | G open/close, arrows select system, H jump |
| General | F1 manual, Esc quit |

Dock when the station is centred, less than 350 metres away, speed below 40, and no pirate is nearby. Start braking early. Buy food on agricultural Lave and sell it on industrial Zaonce to get started.

Progress saves at stations and after trading to `~/.local/share/star-trader/save.json`. Quitting or dying in space preserves your last station save. N on the death screen starts a new pilot and replaces the save.

## Checks

```bash
python3 star_trader.py --self-test
SDL_VIDEODRIVER=dummy python3 star_trader.py --smoke-test
```

The first checks the economy, cargo capacity, and navigation. The second opens and draws five frames using SDL's headless video driver.

## License

MIT. This is an original tribute, not a port of Elite. It includes no original Elite code or assets.
