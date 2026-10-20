# 0.2.23 — top-level Money, VMS and Navigation

- Put Money, VMS, Navigation and Menu in the consistent top navigation bar.
- Add Vessel Management System for status, equipment, fuel, servicing, outfitting, engineering and launch.
- Remove scattered ship-service controls from trading; retain keyboard shortcuts.
- Rename G to Navigation and keep map/search/profile features.
- Preserve in-flight context when browsing hubs and prevent station services being used remotely.

# 0.2.22 — station jobs inside Money

- Remove duplicate Money buttons from station screens.
- Put Station jobs inside Money, with key 5 or J and a clear return to Money.

# 0.2.21 — repair installed updater checkout detection

- Verify a real Git checkout rather than trusting the existence of a .git path.
- Ignore empty placeholders in the installed game folder and follow install-info.json to the source checkout.
- Report a missing recorded checkout clearly while retaining origin/branch/local-edit safeguards.

# 0.2.20 — clearer controls and navigation

- Simplify the header to consistent Controls, Notes, Menu and Back/Save-quit actions.
- Group utility actions in a keyboard/mouse menu with focus highlighting.
- Keep Flight/Nav/Combat/Safety mouse controls in a separate collapsible flight panel.
- Use 32px click targets, updated handbook cards, visible toggle states and cleaner cockpit footer spacing.
- Global utility buttons no longer accidentally trigger job answers or Money actions.

# 0.2.19 — departure access checks and finite station defences

- Warn before launch about refused destination docking, hostile station guns, deep-space destinations and fuel reserves.
- Limit each station to six police ships, with persistent reserves and defeat counts.
- Defeating all six permits docking; station lasers warn for 15 seconds before firing within 2500m.
- Solar shields slow heat buildup but drain above 70% heat; failed shielding exposes the hull. Disable solar-zone shield regeneration.
- Add Money for banking/storage, exchanges, fine payments and one-time code redemption (STAR-TEST-100K grants 100,000 testing credits).
- Add a saved personal Notes notepad with mouse/keyboard scrolling.
- Keep an explicit locked, backed-up offline testing credit-grant command for administration.

# 0.2.18 — unambiguous stocktake answers

- Shortfall and surplus choices always use positive quantities, including when the manifest matches.
- Matching counts now have only one correct option: Matches manifest.

# 0.2.17 — feedback, Crymto and illicit payment deals

- Add Feedback 0: write bugs/suggestions, save offline drafts and open prefilled GitHub issues for manual review/submission.
- Contraband sales normally pay Crymto, a saved account balance retained after destruction and exempt from salvage.
- B buys with credits; C optionally spends Crymto on contraband, then credits for any shortfall.
- N offers an explicit one-tonne clean-credit settlement at a 15% discount.
- Feudal/anarchy exchanges offer disclosed 20% Crymto-to-credit and 10% reverse fees with net previews.
- Increase contraband demand prices so profitable routes remain worthwhile after conversion fees.
- Test report drafts/browser failures, text input, currency payouts, exchange restrictions/fees and death persistence.

# 0.2.16 — detailed planet profiles and economy header

- G then I, or Planet profile, opens a full planet information screen with mouse/keyboard browsing.
- Show demographics, coordinates, economy, government, technology, customs, docking eligibility, facilities and market quotes.
- Keep the map summary compact so information no longer runs off-screen.
- Show the current system economy and technology beside its name in the header.
- Record private planet messages and wanted/for-sale noticeboards as future features.

# 0.2.15 — planet-dependent smuggling margins

- Improve contraband route profits with distinct narcotics and arms supply/demand factors.
- Industrial sources are cheaper; agricultural narcotics demand and frontier arms demand pay more.
- Anarchy/feudal arms premiums and a modest corporate narcotics premium reflect government type.
- Keep dealer buy/sell spreads, customs enforcement and legal-goods pricing unchanged.

# 0.2.14 — daily station jobs and varied questions

- Each station offers 2-3 cargo shifts, 1-2 inventory shifts and one workshop shift per 24-hour cycle.
- Show remaining availability, daily job titles and refresh countdown; persist reservations across reloads.
- Refresh uses real elapsed time, including offline time, without accumulating missed-day shifts.
- Expand workshop to 30 questions, draw five per shift and shuffle answer positions for all job types.
- Vary cargo categories and inventory discrepancies, including matching manifests.
- Preserve active shifts across refreshes and upgrades.

# 0.2.13 — accurate laser hits and visible incoming fire

- Replace the oversized station aim area with hit detection against the drawn hull outlines.
- Resolve the nearest hull first; pirate hits do not also strike a station behind them.
- Asteroids and disabled ships block shots; mining still requires the mining laser.
- Incoming pirate and police attacks show coloured laser beams, muzzle flashes and rearward direction warnings.
- Regression coverage includes near misses, occlusion, pirate kills in front of stations and timed enemy beams.

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
