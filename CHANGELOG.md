# 0.2.2 — cockpit navigation and hyperspace

- Gold navigation dots/brackets and edge arrows track the active destination in front/rear view.
- Top-down scanner shows ships, planets, stations and mines. Click a ship or press 5 to select it; a pink marker tracks its bearing.
- Hold H continuously for a three-second countdown. Releasing H or leaving the cockpit cancels before ignition; jump fuel is spent only at ignition.
- Animated star-stream transit, followed by a five-second arrival banner naming the destination and coordinates.
- Map-to-cockpit charging, fuel revalidation and destination snapshots keep the transition consistent.

# 0.2.1 — laptop controls and rear weapons

- Number-row controls: 1 manual, 2 updates, 3 fullscreen, 4 front/rear view.
- Rear view projects ships, mines and other objects behind the ship.
- Purchasable rear pulse laser (600 credits, tech level 4). Space fires only the weapon fitted for the current view.
- Front weapon selection, ship motion and original saves are preserved.
- Updated in-game help, HUD and documentation.

# 0.2.0 — navigation and ship systems

- Rotating-slot manual docking, collision damage and purchasable docking computer.
- Separate market buy/sell quotes, saved stock, expanded cargo hold and illegal goods.
- Outfitting with technology requirements: beam/military/mining lasers, limited missiles/mines, scoops, energy unit, jammer and cloak.
- Asteroid mining and collectible ore; sun skimming with fuel scoops and overheating.
- Searchable planet profiles, coordinates, arbitrary waypoint locks and navigation display.
- Slow, economical interstellar cruise versus immediate, expensive hyperspace; local fuel consumption and low-fuel warning.
- Cargo affects acceleration, braking, turning, top speed, fuel use and cruise ETA.
- Differing planetary sizes and local flight effects.
- Proximity mines for player/robot ships, stealth/jamming costs, customs, fines and basic robot police encounters.
- Version display, optional daily release notices and a user-run updater that stops on local changes.
- Original save migration, gameplay regression checks and Omarchy launcher verification.
- Separate next-expansion and self-hosted multiplayer roadmaps; the game remains single-player.

Upgrade from the first release: from your checkout, run `git pull --ff-only` then `bash install.sh`. Future updates can use `python3 update.py`. Quit before updating; saves are preserved.
