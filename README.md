# Star Trader

An original Elite-inspired Python space game for **Omarchy**. Trade, mine, fight robot pirates, smuggle contraband and navigate a small wireframe universe. Current version: **0.2.0**.

The current game is offline single-player. Self-hosted multiplayer is a future project; see [MULTIPLAYER.md](MULTIPLAYER.md). The next offline expansion is outlined in [ROADMAP.md](ROADMAP.md).

## Install on Omarchy

```bash
git clone https://github.com/womb4t/star-trader.git
cd star-trader
bash install.sh
```

Open your application launcher and search for **Star Trader**.

The installer uses `omarchy pkg add` only for missing dependencies: Python, SDL2 compatibility libraries, SDL2_ttf and a font. A dependency installation may ask for your password in the terminal. The game installs for your user without sudo. No pip packages are required.

The native window supports Hyprland tiling, resizing and F11 fullscreen. No compositor configuration changes are needed.

## Update

**Upgrading from the first version:** it predates update notices. From your existing checkout, run this once:

```bash
git pull --ff-only
bash install.sh
```

**From 0.2.0 onward:** the game checks the official GitHub release once per day in a background thread. When a newer version is available, it shows an update notice. **F10** displays the installed version and instructions. Checks time out quietly offline; no account, telemetry or mandatory connection is required. Disable checks with `--no-update-check` or `STAR_TRADER_NO_UPDATE_CHECK=1`.

To apply an update yourself, quit the game and run from your checkout:

```bash
python3 update.py
```

Or run the installed updater:

```bash
python3 "${XDG_DATA_HOME:-$HOME/.local/share}/star-trader/update.py"
```

The updater checks the official origin and clean `main` branch, fetches, fast-forwards and reruns installation. It stops on local edits, untracked files or divergent history; it never resets your work. Keep the original checkout available. If you move or delete it, clone again and reinstall. Saved progress is preserved.

## Play

You start docked with 150 credits, a full 7-unit fuel tank, a pulse laser, three missiles and a 20-tonne hold. Food is cheap on agricultural Lave and more valuable on industrial Zaonce. Industrial exports tend to sell well on agricultural worlds. Keep enough credits for fuel and repairs.

| Screen | Controls |
| --- | --- |
| Station | Up/Down select; B buy; S sell; U outfitting; L launch |
| Station services | F buys a full fuel refill; R repairs hull; P pays fines |
| Outfitting | Up/Down browse; B or Enter buy and fit; U returns to market |
| Flight | Arrows steer; W accelerate; S brake, then reverse; Q/E roll |
| Weapons | Space fires selected laser; V cycles installed lasers; M fires a missile; B deploys a mine |
| Equipment | C docking computer; Z signal jammer; K phase cloak |
| Local beacons | D station; P planet; A asteroid/ore; J sun; O collects nearby ore |
| Galaxy map | G open/close; arrows select planet; / searches names; C enters X,Y |
| Free map cursor | Tab switches between planet selection and coordinate cursor; arrows move cursor |
| Course/travel | Enter locks course; H hyperspace; T interstellar cruise; T in cruise cancels |
| General | F1 manual; F10 updates; F11 fullscreen; Esc quit |

### Docking

Fly through the rotating entrance at speed **1–25**. Centre within **14 metres horizontally and 6 metres vertically**, measured in the slot's frame, and use Q/E to keep the slot horizontal within about nine degrees. The cockpit reports roll error. Begin braking early, especially with a loaded hold. A station collision damages shields and hull.

A purchased docking computer handles the approach when the station is ahead, within 2,500 metres, and no hostile ship is present. C or manual steering cancels it.

### Trading, equipment and mining

Buy and sell quotes are separate: BUY is what you pay, SELL is what you receive. Station stock is finite and saved. Cargo reduces top speed, turning rate, acceleration and braking, and increases fuel consumption. A larger hold increases capacity to 35 tonnes.

Outfitting availability depends on local technology. You can buy a beam laser, military laser, mining laser, missiles, mines, scoops, an energy unit, docking computer, jammer or cloak. Installed lasers can be switched with V. Ammunition must be replaced; missiles and mines each have four storage slots. Browse down to see all equipment.

Use A to find an asteroid, select a purchased mining laser with V, and fire until it breaks up. Approach the fragments at speed 50 or below. With scoops fitted, O collects one tonne of ore within 260 metres; sell ore at a station. Ordinary lasers do not yield ore.

### Navigation and fuel

Every planet has galactic coordinates and a searchable profile showing economy, government, technology, population and diameter. Search with / and press Enter to lock the first match. C accepts an arbitrary coordinate such as `4.5,6.2`, within 0–10 on both axes. The locked waypoint appears in navigation and is saved when docked.

The map shows both travel choices for your current load:

- **Hyperspace:** immediate arrival, costing `1.2 × distance + 0.2` fuel.
- **Cruise:** `45 × distance × cargo mass factor` seconds of game time, costing `0.25 × distance × cargo mass factor` fuel. T cancels at your current coordinates.

These are game-scale distances/timings. Local flight also consumes fuel. The 7-unit tank no longer guarantees a seven-light-year jump. Low reserves trigger a warning; fuel can run out. F at a station buys a refill at 3 credits per unit, independently of hull repairs. Scoops can gather fuel near the sun: J selects its beacon, skim within 500 metres at speed 10–60, and retreat before heat reaches 90. Empty-space coordinates have no station or services. If stranded without a viable fuel source, quit and resume from the last station save.

### Combat, stealth and smuggling

Robot pirates can attack from ahead or astern; missiles and mines can help against pursuers. Mines arm after 1.5 seconds, persist for 75 seconds and detonate on hostile proximity. Their blast can damage the ship that deployed them. Robot pirates can deploy mines too.

The bought signal jammer (Z) disrupts targeting for eight seconds, costs 0.05 fuel and has a 20-second cooldown. The bought phase cloak (K) prevents robot targeting while active, burns 0.012 fuel per second and slows shield regeneration. Firing a laser or missile, or deploying a mine, drops the cloak. These are original game mechanics rather than reproductions of Elite's anti-missile ECM.

Narcotics and unlicensed arms are marked `*` in the market. Regulated stations may inspect arriving cargo, confiscate contraband and issue fines. Frontier anarchies/feudal worlds do not run these checks. Outstanding fines can attract robot police; destroying a police ship increases the fine rather than paying a bounty. P at a station clears a fine if you can afford it.

## Saves and files

Game files install under `${XDG_DATA_HOME:-~/.local/share}/star-trader/`. The launcher is in the same data directory under `applications/star-trader.desktop`.

The save is `star-trader/save.json`. Docking, trades and station purchases save automatically. Original saves are migrated, preserving cash, cargo, equipment and location. Quitting or dying in space retains your last station save. N on the death screen starts a new pilot and replaces the save. Back up `save.json` before experimenting with it.

Remove installed code and launcher while keeping your save:

```bash
data_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -f "$data_dir/applications/star-trader.desktop"
rm -f "$data_dir/star-trader/star_trader.py" "$data_dir/star-trader/update.py"
rm -f "$data_dir/star-trader/README.md" "$data_dir/star-trader/LICENSE" "$data_dir/star-trader/install-info.json"
```

## Development checks

```bash
python3 star_trader.py --version
python3 star_trader.py --self-test
python3 -m unittest -v test_game test_updater
SDL_VIDEODRIVER=dummy python3 star_trader.py --smoke-test
```

You can run `python3 star_trader.py` directly without installing. System libraries and a supported font still need to be present. Rendering uses system SDL2 and SDL2_ttf through Python ctypes.

## License

MIT. An original tribute, not a port of Elite; no original Elite code or assets are included. The galaxy is currently eight predefined planets, not the original's generated galaxies. Several flight and combat mechanics are deliberately simplified.
