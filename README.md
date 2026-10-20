# Star Trader

An original Elite-inspired Python space game for **Omarchy**. Trade, mine, fight robot pirates, smuggle contraband and navigate a small wireframe universe. Current version: **0.4.0**.

Play offline, or use the optional **private progress server** to save separate tester accounts on an iMac or another Python host: [SERVER.md](SERVER.md). Shared flight and combat are a future project; see [MULTIPLAYER.md](MULTIPLAYER.md). The next offline expansion is outlined in [ROADMAP.md](ROADMAP.md).

## Install on Omarchy

```bash
git clone https://github.com/womb4t/star-trader.git
cd star-trader
bash install.sh
```

Open your application launcher and search for **Star Trader**. The splash screen offers **Online play**, **Offline play**, and **Connection settings**. Existing Star Trader Online launchers are migrated into this single entry.

The installer uses `omarchy pkg add` only for missing dependencies: Python, SDL2 compatibility libraries, SDL2_ttf and a font. A dependency installation may ask for your password in the terminal. The game installs for your user without sudo. No pip packages are required.

The native window supports Hyprland tiling, resizing and 3 fullscreen. No compositor configuration changes are needed.

## Update

**Upgrading from the first version:** it predates update notices. From your existing checkout, run this once:

```bash
git pull --ff-only
bash install.sh
```

**From 0.2.0 onward:** the game checks the official GitHub release once per day in a background thread. When a newer version is available, it shows an update notice. **2** displays the installed version and instructions. Checks time out quietly offline; no account, telemetry or mandatory connection is required. Disable checks with `--no-update-check` or `STAR_TRADER_NO_UPDATE_CHECK=1`.

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
| Station | Up/Down select; B buy; S sell; U outfitting; L requests departure clearance, then L launches once granted |
| Station services | F buys a full fuel refill; R repairs hull; P pays fines |
| Outfitting | Up/Down browse; B or Enter buy and fit; U returns to market |
| Flight | Arrows steer; W accelerate; S brake, then reverse; Q/E roll |
| View | 4 toggles front/rear view; Space fires the current view’s fitted laser |
| Weapons | Space fires selected laser; V cycles installed lasers; M fires a missile; B deploys a mine |
| Equipment | C docking computer; Z signal jammer; K phase cloak |
| Safety and radio | 6 distress/recovery; 7 requests docking clearance; 8 engineering and training |
| Bank/storage | 9 while docked; D deposit money, W withdraw; S store selected cargo, T retrieve; R rent, B buy bay |
| Local beacons | D station; P planet; A asteroid/ore; J sun; O collects nearby ore |
| Galaxy map | G open/close; arrows select planet; / searches names; C enters X,Y |
| Free map cursor | Tab switches between planet selection and coordinate cursor; arrows move cursor |
| Course/travel | Enter locks course; hold H for 3 seconds to enter hyperspace; T interstellar cruise; T in cruise cancels |
| Scanner | Click a ship contact to select it; 5 selects/clears the current ship target |
| General | 1 manual; 2 updates; 3 fullscreen; Esc quit |

### Mouse controls

Mouse selection is available throughout the game: click commodity/equipment rows, then the buy/sell/fit buttons; click planets or empty coordinates on the map; click scanner contacts; select rescue offers and use the accept/negotiate/refuse buttons. Screen buttons cover departure, docking, station services, training, repair, travel and returning from menus. Search and coordinate fields still support normal keyboard text entry; clicking the map selects a destination without typing.

Press **1** for the redesigned pilot handbook: six clickable tabs with control cards rather than a text wall. Left/Right switches pages. In flight, click **Actions** for a compact cockpit panel with **Fly**, **Nav**, **Fight** and **Safety** tabs. Hold a movement, roll or fire button to keep it active; releasing the mouse stops that input. Hold **Hold jump** for the same three-second hyperspace countdown as H. A click can also use weapons, jamming, cloaking, beacons, the radio and engineering. **FS** toggles fullscreen; **X** quits or **<** goes back from a modal screen. Losing window focus releases held inputs.

### Docking and departure clearance

L first checks fuel and the locked destination's jump requirement, including a conservative local-approach reserve. An empty/low tank or insufficient destination fuel opens a warning: refill, cancel, or explicitly proceed. The warning can be overridden; it is not a mandatory refuelling purchase.

After requesting departure, wait two seconds for clearance, then press L (or click Launch) to leave. Cancelling keeps you docked.

Before docking, press **7** or use **Radio 7** in Actions. Station control responds after two seconds if within 10,000 metres. Clearance lasts 120 seconds. A docking computer requests clearance automatically. Regulated stations refuse pilots with outstanding fines of 100 credits or more; anarchy and feudal ports still accept them. Profiles show the current docking policy for your pilot. Departure from a station where you are already docked remains permitted.

Fly through the rotating entrance at speed **1–25**. Centre within **14 metres horizontally and 6 metres vertically**, measured in the slot's frame, and use Q/E to keep the slot horizontal within about nine degrees. The cockpit reports roll error. Begin braking early, especially with a loaded hold. A station collision damages shields and hull.

Without valid clearance, even a geometrically correct entry will be rejected as a collision. A purchased docking computer handles the approach when the station is ahead, within 2,500 metres, and no hostile ship is present. C or manual steering cancels it.

### Trading, equipment and mining

Buy and sell quotes are separate: BUY is what you pay, SELL is what you receive. Station stock is finite and saved. Cargo reduces top speed, turning rate, acceleration and braking, and increases fuel consumption. A larger hold increases capacity to 35 tonnes.

Outfitting availability depends on local technology. You can buy a beam laser, military laser, mining laser, missiles, mines, scoops, an energy unit, docking computer, jammer or cloak. Front lasers can be switched with V. A rear pulse laser costs 600 credits at tech level 4 or above. Press 4 for rear view, then Space to fire it; no rear laser means no rear firing. Rear view does not change your ship’s course or flight controls. Ammunition must be replaced; missiles and mines each have four storage slots. Browse down to see all equipment.

Use A to find an asteroid, select a purchased mining laser with V, and fire until it breaks up. Approach the fragments at speed 50 or below. With scoops fitted, O collects one tonne of ore within 260 metres; sell ore at a station. Ordinary lasers do not yield ore.

### Navigation and fuel

Every planet has galactic coordinates and a searchable profile showing economy, government, technology, population and diameter. Search with / and press Enter to lock the first match. C accepts an arbitrary coordinate such as `4.5,6.2`, within 0–10 on both axes. The locked waypoint appears in navigation and is saved when docked.

The map shows both travel choices for your current load:

- **Hyperspace:** hold H continuously for a visible three-second countdown, followed by a 1.6-second star-stream transition and arrival banner. Releasing H or leaving the cockpit before ignition cancels without spending jump fuel. Fuel is rechecked and deducted at ignition. Normal flight and threats continue during charging. Jump cost is `1.2 × distance + 0.2` fuel.
- **Cruise:** `45 × distance × cargo mass factor` seconds of game time, costing `0.25 × distance × cargo mass factor` fuel. T cancels at your current coordinates.

The cockpit has a top-down scanner: your ship is white at its centre, front is toward the top, pirates are red, police/planets blue, and the station green. Its radius is 2,500 metres, with more distant contacts clamped to the rim. Click a ship dot or press 5 to select it; the selected ship gains a gold scanner ring and a pink cockpit marker. Click the station/planet to select its local navigation beacon.

The active navigation destination has a gold dot/bracket when visible and an edge arrow when outside the view. Rearward targets are labelled “BEHIND: 4”; toggle rear view to see them. A remote locked galaxy waypoint shows a compass course; H/T travels between galactic coordinates. Once there, local beacons guide normal flight toward the station, sun, planet or ore. Steering in local space does not change galactic coordinates.

These are game-scale distances/timings. Local flight also consumes fuel. The 7-unit tank no longer guarantees a seven-light-year jump. Low reserves trigger a warning; fuel can run out. F at a station buys a refill at 3 credits per unit, independently of hull repairs. Scoops can gather fuel near the sun: J selects its beacon, skim within 500 metres at speed 10–60, and retreat before heat reaches 90. Empty-space coordinates have no station or services. If stranded without a viable fuel source, press 6 to request rescue and review salvage terms.

### Distress calls, salvage and rescue

Press **6** in flight or cruise, or click Distress. A call stops cruise and opens recovery offers. Broadcasting reveals a cloaked ship. Calls have a 60-second in-flight cooldown; declining an offer takes no payment.

Within **5,000 metres** of a station that accepts your pilot, the **Galactic Recovery Accord** charges a fixed **25% of credits AND cargo tonnes**, rounded up and capped at what you hold. The screen lists the exact cash amount and each cargo item claimed before you accept. Equipment is not part of the salvage claim.

Beyond coverage, or where local authorities refuse a wanted pilot, three robot salvagers quote independent percentages. Select an offer, press N or click Negotiate to counter up to twice per rescuer, and accept or refuse the resulting terms. Private quotes can be reduced but never below 25%. No payment occurs without acceptance.

Accepting applies the claim once, tows you to an accepting station, fills the fuel tank, stabilises hull to at least 25%, and docks/saves. Existing equipment is preserved; remaining damage still needs repair. Station customs may confiscate illegal cargo separately. A pilot with no credits/cargo is still rescued, with a zero salvage claim. Wanted pilots are routed to a port that will admit them.

### Maintenance and engineering

Each actual station departure adds `1 + 0.025 × cargo tonnes` maintenance wear and increments flights since service. Routine service costs 0.25 credits per wear point; hull work costs 0.35 credits per missing hull point, with the combined quote rounded up once. A healthy ship has no neglect breakdown risk on its first four departures after service; damaged hulls below 80% still carry risk. Once the ship is neglected (at least five departures, or hull below 80%), each departure rolls a breakdown chance that increases with wear, flight count and existing hull damage. The engineering screen and departure screen show the next-flight risk. A breakdown stops the drive and disables cruise/hyperspace; weapons and the distress radio remain usable. Station **R / Service** repairs hull and resets wear and the flight counter, charging for both damage and wear. Travelling or being towed between systems does not count as an extra departure.

Press **8 / Skills** for engineering. Buy levels 1–5 at a station for 200, 400, 800, 1,600 and 3,200 credits. Higher skill improves field-repair probability, hull restoration and wear reduction. Parts cost **15 credits per attempt**. Field repairs can clear a breakdown and repair your own ship; station servicing remains more thorough.

Disabled robot ships sometimes appear in local space. Select their gold scanner contact (or cycle targets with 5), get within **350 metres** and slow to **30 or less**. In engineering, choose Help target / H to attempt assistance. Success earns a crew payment; failure uses the same repair cooldown as working on your own ship. Repair parties cannot work with an active hostile present.

A failed attempt imposes a **real-time** wait: **30 minutes, then 60, 120, 240…** for consecutive failures. A successful attempt resets the failure sequence. Cooldowns are tied to the commander and stored immediately in an engineering ledger, so restarting or reloading the previous station save does not skip the wait. A new pilot has a separate identity. Field-repair outcomes, cargo and crew rewards are retained by the live autosave and on exit. There is no need to wait out a cooldown to call for distress rescue.

### Bank and station storage

Press **9** or click **Bank / storage** while docked. The galactic bank holds credits off-ship; select 10, 50, 100 or All, then deposit or withdraw. Deposited money is not part of a distress salvage claim. Cargo bays belong to individual stations: renting costs **50 credits for 40 tonnes for seven real days**, while buying costs **750 credits for 100 tonnes**. Owned capacity has no recurring rent in this version.

Choose a commodity, then store/retrieve one tonne. Expired rentals keep their contents and allow retrieval; renew or buy to deposit more. Buying a rented bay retains its cargo and increases capacity. A bay at one port cannot be accessed from another. Station cargo and bank money survive ship loss; N explicitly starting a new pilot resets all assets. This version stores cargo, not spare ship modules.

Owning/renting whole storage centres, collecting rent from other players, selling bays off-plan to fund a station, armed personal bases and fleets are recorded **future** features in [MULTIPLAYER.md](MULTIPLAYER.md) and [ROADMAP.md](ROADMAP.md).

### Collisions, announcements and quitting

Ships have swept collision checks: crossing a hull between frames still causes impact damage to both ships and a bounce. There is a brief contact cooldown to prevent repeated damage from one overlap. Critical warnings have a boxed announcement with a flashing border; text remains readable.

The game saves live flight/world state **every two seconds**, on major damage/threat events, on station transactions and on clean exit. It retains position, velocity, shields/hull, nearby contacts/mines, cargo, travel/autopilot state and death. Quitting no longer rolls back to the previous station. Only one running game may use a save at a time.

On rejoining an undocked ship, a bounded **offline catch-up simulation** advances elapsed time: the ship keeps moving, autonomous docking/travel can complete, threats can attack, fuel can run out, and the ship can be destroyed. Human control inputs are released, not replayed. The detailed offline simulation is limited to **40 minutes**; if still adrift after a longer absence, emergency recovery applies the station 25% salvage rate or a 50% private claim and tows to an accepting station. These local catch-up rules are an offline approximation, not an always-running multiplayer universe. Dock before quitting for a safe logout.

A destroyed ship stays destroyed across restarts. **R / Recover starter ship** explicitly obtains a replacement for up to **100 bank credits**, losing carried credits/cargo, fitted equipment and ammunition but retaining station storage, remaining bank funds and the pilot's training. **N / New pilot** resets everything. The future server will keep uncaptained ships in its live simulation, with reconnect attaching to the surviving ship or reporting its destruction; see the multiplayer roadmap.

### Combat, stealth and smuggling

Robot pirates can attack from ahead or astern; missiles and mines can help against pursuers. Mines arm after 1.5 seconds, persist for 75 seconds and detonate on hostile proximity. Their blast can damage the ship that deployed them. Robot pirates can deploy mines too.

The bought signal jammer (Z) disrupts targeting for eight seconds, costs 0.05 fuel and has a 20-second cooldown. The bought phase cloak (K) prevents robot targeting while active, burns 0.012 fuel per second and slows shield regeneration. Firing a laser or missile, or deploying a mine, drops the cloak. These are original game mechanics rather than reproductions of Elite's anti-missile ECM.

Narcotics and unlicensed arms are marked `*` in the market. Regulated stations may inspect arriving cargo, confiscate contraband and issue fines. Frontier anarchies/feudal worlds do not run these checks. Outstanding fines can attract robot police; destroying a police ship increases the fine rather than paying a bounty. P at a station clears a fine if you can afford it.

## Saves and files

Game files install under `${XDG_DATA_HOME:-~/.local/share}/star-trader/`. The launcher is in the same data directory under `applications/star-trader.desktop`.

The save is `star-trader/save.json`. Per-commander repair cooldowns are stored alongside it as `engineering-<commander-id>.json`; back these up with the save. Live flight and station transactions save automatically, including clean exits and destruction. Original saves are migrated, preserving cash, cargo, equipment and location. The `_session` section records the current simulation for restart/catch-up. N on the death screen explicitly starts a new pilot and replaces all assets. Back up `save.json` before experimenting with it.

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

Approach guidance: Y toggles centring on the selected local navigation target ahead.
You retain throttle and roll control; arrows cancel guidance. It does not grant docking clearance.
Use H/T for remote galaxy destinations. I toggles fine steering (20% arrows and Q/E roll),
useful for docking. Mouse: Actions > Nav > Guide Y; Actions > Safety > Fine I.

Docking allows +/-14 degrees of roll error. Slow station contact (speed 25 or below)
causes minor damage; high-speed impacts remain dangerous. Slot roll error stays visible after clearance.

Station defence: approaching the docking lane without clearance triggers warnings,
then hostility after 12 seconds. Stop outside the entrance, withdraw or obtain clearance
with 7 before escalation. Shooting the station causes immediate hostility, a 150cr fine,
revoked clearance and attacking police. Hostility at that station survives saving;
leave for another accepting port. Paying fines alone does not clear station hostility.

Arrows now turn the ship heading rather than sliding sideways. Objects and stars
move opposite your turn; forward thrust follows the new heading. I reduces turn
and roll rates for docking. The top-view radar follows cockpit roll and rear view:
ahead is up, behind is down, left/right match the view. The TARGET BEARING panel
shows a selected ship or navigation target relative to your nose: steer toward the
gold dot until it reaches the centre box. TURN cues show which arrow to use.

STRANDED AT A STATION? Press J or click Station jobs while docked.
Cargo handling (60s): 15-25 cr. Inventory checks (75s): 20-35 cr.
Workshop assistant (90s): 25-40 cr and 10 workshop XP. No fuel, equipment
or upfront money required. Choose a job and answer five tasks with 1/2/3
or the mouse. Payment arrives after the shift timer and tasks finish.
Mistakes reduce only the bonus. Leaving pauses work; saved shifts resume
when you reopen J, with no offline pay. Workshop practice adds at most five
percentage points to repair probability; engineering levels still require training.

Station jobs: use the top Jobs J button from the market, outfitter or bank.
On the job list click a job card or use Up/Down then Enter; 1/2/3 also works.

Mouse input uses SDL logical event coordinates directly, so buttons, map picks
and scanner selections stay aligned when the window is scaled or letterboxed.

Laser hits follow the visible hull outlines and stop at the nearest ship,
station or asteroid. Shooting a pirate in front of a station does not hit
the station too; stray shots that actually strike its hull remain hostile acts.
Incoming pirate/police fire shows a coloured beam and firing flash, or an
incoming-fire direction marker when the attacker is behind your view.

Station jobs now have daily limits at each station: 2-3 cargo shifts,
1-2 inventory shifts and one workshop shift. Boards refresh every 24 real
hours from first access, including time spent offline; unused shifts do not
accumulate. The board shows remaining shifts and the refresh countdown.
Accepting reserves a shift immediately; limits persist after reloading.
An unfinished shift can still be completed after the board refreshes.
Workshop shifts draw five questions from a pool of 30; answer positions are
shuffled. Cargo labels and inventory counts vary too. Existing active shifts
are preserved when updating.

Contraband rewards depend on the planet: industrial worlds are cheaper sources,
agricultural worlds pay more for narcotics, and frontier worlds have strong arms
demand. Anarchy/feudal governments add an arms premium; corporate states add
some narcotics demand. Normal dealer spreads and customs risks still apply.

Detailed planet profiles: G opens the map; select a named planet and press I
or click Planet profile. View coordinates, government, population, size, tech,
customs, docking access, station services and all commodity buy/sell prices.
Left/Right or Previous/Next browses profiles without changing your waypoint.
I or the Back button returns to the map. The main header shows your current system
name, economy and technology level, with credits/kills below.

FEEDBACK: click Feedback 0 or press 0, choose Bug report or Suggestion,
then type a description. Save draft keeps an offline copy under the game data
folder in feedback/. Open GitHub draft opens a prefilled issue for you to
review and submit (GitHub sign-in may be required). Only your text, game
version, platform, screen and system are included; no save file is attached.

CRYMTO (CYM): contraband sales normally pay this separate account balance.
Crymto survives ship destruction and is exempt from salvage claims. B always
buys with credits; C at the market buys contraband with Crymto first, with
credits covering any shortfall. Ordinary shops, fuel and banks use credits.
N negotiates a one-tonne contraband sale for clean credits at a 15% discount;
review the offer and press Y to accept. E opens the exchange at feudal and
anarchy ports: Crymto -> credits costs 20%; credits -> Crymto costs 10%.
Conversion previews show net proceeds before you choose to convert. Exchange
proceeds round down to whole units. Smuggling demand prices include room
for these fees; route choice still matters.

Departure checks warn if a locked destination will refuse docking or has no station.
Each station has six police ships, with reserve counts in its planet profile.
Reserves and defeats persist after reloading and do not refill automatically.
Destroying all six permits docking despite hostility/fines, but station lasers
warn for 15 seconds before firing within 2500m. Withdraw or dock promptly.
Fuel scoops collect at 150-500m from the sun, speed 10-60. Shields slow heating;
above 70% heat radiation drains them, and hull damage follows shield failure.
90% is the thermal danger limit. Shields do not recharge inside the solar zone;
move beyond 600m to cool down and recharge.
For offline testing only, close the game then run star_trader.py
--grant-test-credits 100000. It backs up the save and adds credits without
altering fines, Crymto or ship position. Multiplayer grants will require server admin authority.

MONEY AND NOTES: 9 opens Money for bank/storage, Crymto exchange, fine payments
and credit codes. Select Redeem code and enter STAR-TEST-100K for a one-time
100,000-credit grant per pilot in this offline test build. Multiplayer codes
will require server validation. Press - or click Notes for a saved personal
notepad; typing appends text, Enter adds a line, arrows/Earlier/Later scroll,
and Save notes or returning records changes. Notes survive ship loss.

CONTROLS: the top bar offers Money, Nav, VMS, Menu and Back/Quit.
Menu groups Controls, Notes, reporting, updates, fullscreen and exit. The grave/backtick key opens
Menu; arrows and Enter select items, Back returns. Escape always saves and closes. The flight-only bottom-left
Flight controls button opens Flight/Nav/Combat/Safety mouse controls. Buttons
use consistent 32px targets, clear labels and context-specific actions.

Open Money (9) then Station jobs (5) to earn credits. Jobs return to Money.

VMS (Vessel Management System) is in the top bar, alongside Money and
Navigation. X opens VMS: check hull/shields, fuel/heat, cargo/mass, maintenance,
weapons and fitted equipment. While docked, buy fuel, service, fit equipment,
train engineering and launch from VMS. In flight, view status and open field
engineering; station facilities stay unavailable until docking. Money (9) is
also viewable in flight, with financial services restricted to stations.
Nav is the name for G; its map, search and planet profiles remain.

Top navigation order: Money, Nav, VMS, Menu. Bottom action bars use compact
buttons with separate keyboard badges, consistent spacing and right-aligned
Return/Cancel controls. Crowded screens wrap actions into two rows.

Code entry supports Ctrl+V paste, Ctrl+C copy, Ctrl+X cut and Ctrl+A select
all, plus Paste/Copy/Select all buttons. Notes and feedback accept these
shortcuts too. Heat now has its own flight instrument with shield protection
and the 90% danger marker; VMS fuel is shown separately.

Proximity mines cost 75 credits and require tech level 4; maximum four.
Outfitting shows the local/required tech levels even for ammunition.

## Station hostility cooldown

Station hostility cools after 30 minutes away from the station (more than 10,000 metres, deep space, or another system). Remaining nearby resets the timer; further attacks restart it. Planet profiles show the remaining wait. Outstanding fines and police reserves do not reset.

## Emergency close

Escape always saves and closes the game immediately, from every screen, including text entry and hyperspace. Click Back, Return or Cancel to navigate without quitting. In-flight logout still preserves your position and unattended recovery rules.

## One launcher, online or offline

The opening screen uses the supplied Star Trader splash artwork, fitted without cropping. Click Online play or Offline play, or use arrows and Enter. Online means private-server progress saving; shared flight and combat remain future work. Offline and server-account saves remain separate. Escape closes the opening screen without changing either save.

Connection settings let you edit the server address, private token **file path**, trusted-LAN HTTP permission and first-account import option. Tab switches fields; Ctrl+V pastes; Enter saves. Settings live in `~/.config/star-trader/connection.json` (or XDG_CONFIG_HOME). The token itself remains in its private file. The installer migrates the old `~/.local/bin/star-trader-online` settings as data and removes its duplicate application menu entry. A failed connection leaves the chooser available so you can retry or play offline. `--offline` skips the chooser for direct offline launch; server CLI flags still prefill an online connection.

The installer includes the artwork as a compressed BMP so no new runtime image libraries are needed. Source PNG supplied by the project owner: `assets/star-trader-splash.png`.
