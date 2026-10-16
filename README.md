# Star Trader

A compact, original Elite-inspired space trading game written in Python. Fly a wireframe spaceship, trade across eight star systems, fight pirates, and dock to save your progress.

## Run

```bash
python3 star_trader.py
```

Requires Python 3, SDL2, SDL2_ttf, and either JetBrains Mono Nerd Font or DejaVu Sans Mono. No Python packages or internet connection are needed to play. Tested on Linux with Python 3.14.

On Arch Linux / Omarchy, dependencies are available with:

```bash
sudo pacman -S python sdl2 sdl2_ttf ttf-dejavu
```

On Debian / Ubuntu:

```bash
sudo apt install python3 libsdl2-2.0-0 libsdl2-ttf-2.0-0 fonts-dejavu-core
```

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
