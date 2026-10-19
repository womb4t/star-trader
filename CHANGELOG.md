# 0.2.12 — fix mouse clicks in scaled windows

- Remove the second mouse-coordinate conversion: SDL already scales events to the game resolution.
- Restore aligned button, map and scanner hit detection in resized/scaled windows.
- Add a real SDL event regression covering four window sizes, letterboxing, jobs, answers and held controls.

# 0.2.11 — visible station job selection

- Add a prominent top Jobs J button at the market, outfitter and bank.
- Allow J from the bank, and highlight clickable job cards.
- Add Up/Down and Enter job selection alongside mouse and 1/2/3 shortcuts.

# 0.2.10 — dockside jobs for stranded pilots

- J opens repeatable paid cargo-handling, inventory and workshop shifts while docked.
- No fuel, equipment or upfront credits required; five tasks and a 60/75/90-second shift.
- Guaranteed base pay; correct answers increase bonuses to 25/35/40 credits.
- Workshop XP grants a small capped repair-chance bonus without unlocking engineering levels.
- Saved shifts pause outside the jobs screen; completed payouts cannot be claimed twice.
- Mouse controls, station buttons and handbook instructions included.

# 0.2.9 — connected steering and flight instruments

- Arrows turn heading rather than strafing; stars and local objects rotate together, preserving range.
- Y approach guidance turns toward the target while leaving throttle and roll manual.
- Radar uses the cockpit coordinate frame, including roll and rear view, with ahead/behind labels.
- Target bearing instrument displays horizontal/vertical direction and explicit TURN cues.
- Fine controls and cargo mass continue to reduce turn rates.

# 0.2.8 — station warnings and police defence

- Uncleared docking approaches receive immediate and six-second warnings, escalating at 12 seconds.
- Stop outside the entrance, withdraw or obtain clearance to avoid escalation.
- Station laser hits immediately cause hostility, revoke clearance and trigger attacking police.
- Hostility and a one-time 150cr offence fine persist in saves; hostile stations refuse docking.
- Station defence reuses the active combat contact and queues dispatch if another enemy is present.

# 0.2.7 — more forgiving docking

- Add five degrees of roll allowance each side: docking now accepts +/-14 degrees.
- Gentle station contact at docking speeds causes minor damage; fast impacts remain dangerous.
- Keep slot alignment visible after docking clearance; improve collision recovery guidance.

# 0.2.6 — approach guidance and fine docking controls

- Y toggles local target centring, with manual throttle and station-slot roll; arrows cancel.
- I toggles 20% steering and roll sensitivity for precise docking adjustments.
- Mouse toggles, cockpit indicators, handbook instructions and saved assist settings.
- Galactic courses still require H/T; guidance disengages for unavailable or rearward targets.

# 0.2.5 — collisions, persistent risk, bank and storage

- Swept ship collisions, mutual damage/bounce and visible flashing announcements.
- Live two-second autosaves, exact clean-exit snapshots, persisted death and single-instance save protection.
- Offline unattended catch-up (up to 40 minutes); prolonged undocked absence triggers emergency salvage rather than a free station rollback.
- Bank deposits, local rented/owned cargo bays, protected stored assets and an explicit starter-ship recovery after destruction.
- Pilot handbook rebuilt as clickable tabbed cards; cockpit Actions grouped into Fly/Nav/Fight/Safety.
- Future plans recorded for uncaptained multiplayer ships, owned storage centres, tenant rentals, off-plan station funding, armed bases and fleets.

# 0.2.4 — gentler starter-ship maintenance

- Halve departure wear and routine servicing rates; hull repairs cost 30% less.
- A healthy ship gets four departures after service before neglect can cause a breakdown.
- Lower flight-count/wear contributions to breakdown probability; badly damaged ships still carry risk.
- Service quotes and actual charges use the same calculation. Existing saves receive the new pricing without conversion.

# 0.2.3 — recovery, engineering, station traffic and mouse controls

- Low/empty-fuel and destination-fuel warning before departure, including local approach reserve.
- Station departure requests and time-limited docking clearance; regulated ports can refuse wanted pilots.
- Distress calls: fixed 25% cash/cargo salvage within 5,000m of accepting stations, negotiated robot offers elsewhere.
- Explicit fee review, single settlement, equipment preservation and rescue even with zero cash/cargo.
- Maintenance wear and successive-flight breakdown risk; station service resets wear and flight count.
- Purchased engineering skill, probabilistic own-ship/disabled-ship repairs, crew rewards and commander-specific persistent failure cooldowns (30, 60, 120... real minutes).
- Clickable trade/equipment/map/scanner/offer selection, screen actions and a held-input cockpit panel for mouse flight, weapons and hyperspace.
- Original save migration, regression checks and rendered screen verification.

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
