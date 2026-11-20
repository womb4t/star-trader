# 0.9.6 — long-range scanner

From your suggestions:
- **Long-range scanner** (outfitting, 900 cr, tech 6). Ctrl+L or the RNG button on the radar switches between 2.5 km and 25 km. On long range, contacts sit at their true range instead of piling up on the rim, and ships in distress are found from much further away. With the DSC console fitted, the selected caller shows its identity and range on the radar ("235 104 377 6.5 km"); the radar's bottom line shows the range to whatever you have selected.

# 0.9.5 — the Relay ticker

New:
- **The Relay's news ticker** runs along the bottom of every screen, cockpit included: Council decrees, the STA Tally and galactic events. News travels over the subnet; during a solar flare only local news gets through. The window is 30 pixels taller to make room.
- **The splash screen holds for 4 seconds** before online play connects by itself. Any key still stops the countdown.

From your suggestions:
- **Classic steering.** LEFT / RIGHT now roll the ship and UP / DOWN pitch it: roll, then pull up to turn. Q / E are now the rudder for flat turns. Docking: roll with LEFT / RIGHT to match the slot.
- **Scooping shows your totals:** "Scooped 1 t of ore. 5 t aboard, hold 12/20 t."
- **Cargo canisters keep their secrets.** Cargo spilled from ships shows as CANISTER on radar; you find out what's inside when you scoop it. Rock fragments show ORE, GOLD or SILVER.
- **Shake a pirate off your tail.** Brake hard and a pirate behind you overshoots into your sights. Pirates on your tail also make firing passes every few seconds.

From your bug reports:
- **Pirates no longer lock onto your side or tail.** A pirate behind you was pulled back to the same spot every frame, so turning towards it could never bring it into the crosshairs. Once out of missiles, you could not win the fight. Turning now swings pirates round into view.

# 0.9.4 — scoops and rocks

From your bug reports:
- **Scooping takes time.** Scoops now draw in one piece at a time, 4 seconds a tonne, while you stay slow (50 or below) and within 260 m. The HUD shows progress; speeding up or flying off loses the piece being drawn in. O shows what the scoops are doing.
- **Rock fields don't refill on every launch.** The rocks near each station grow back one at a time, 30 minutes after being cut, so mining, docking and relaunching no longer refills the field.
- **A refused jump tells you what to do.** If you lack fuel to jump, the message says what interstellar cruise (T) would cost instead (slower but cheaper), or to refuel. Best-in-range prices assume a full tank, so a far destination may need cruise or a refuel.

# 0.9.3 — full statement

From your suggestions:
- **The trade log is now a full statement (Money, then T, or 6).** Besides market trades it lists every payment and receipt: kit bought and sold, fuel, service and repair parts, bays, engineering training, fines, bribes, salvage and recovery fees, credits lost with a ship, station jobs, assists, bounties, the Crymto exchange and bank transfers. Each line shows money in or out and your balance after it. Payments made partly in Crymto show a line for each currency. It keeps the last 200 entries.

# 0.9.2 — money reports

From your suggestions:
- **Money / Reports (Money, then E).** Shows where your money came from and went (trading, bounties, jobs, running costs, fines, rescue fees and lost ships) for today, the last 7 days or all time. It also shows your earnings per hour and per trip next to the average commander, with a few lines on what is costing you most. Averages appear once 3 commanders have played in the period; the server only ever sends averages, never another commander's figures. Records start with this version.
- **The trade log has In, Out and Balance columns**, and totals money in and out at the top.
- **Sell your ship's kit.** In Outfitting, S sells the selected item back for half its new price: lasers, mounts, scoops, the cargo bay (once the hold is down to 20 t), docking computer, missiles and mines. Selling a laser puts the built-in pulse laser back on that mount. Buying a laser now tells you the pulse laser is kept: V switches lasers, and a rear laser mount carries one behind you.

- **Screen buttons down the right-hand side** for 5 Comms, 6 Trades, 8 Engineering, 9 Manual and 0 Home, so the screens past 1–4 are easy to find. The window is a little wider to make room.
- **Newcomer Charter.** Until Operator rank, legal sales at Halvora, Meridel and Brennix (low-tech, well-policed worlds) pay half your profit again, up to 40 cr a tonne, and Charter patrols turn many pirates away there. The Charter ends at Operator, pointing you to the core worlds.
- **Settle with the police by radio.** If flying too close to a station was your only offence and you have not fired on the police, R now pays your fines on the spot: the police stand down and you are cleared to dock. Without the money you surrender as before. The warning before police launch is now 20 seconds instead of 12.
- **Prices hold steadier between stops.** Deliveries by other traders and station production now reach prices over about half an hour, so a margin you saw at one station is mostly still there after a stop on the way. Your own trades still move prices at once.
- **Crymto goes further.** Anarchy and feudal ports take Crymto for anything (market goods, kit, fuel, service, bays, training and fines), spending it before credits. Every station now has a Crymto exchange: cashing Crymto costs 20% at lawless ports, 30% under dictatorships, communists and confederacies, and 40% in democracies and corporate states. Lawful ports also run compliance checks, more often where the Council funds more police: a check freezes half the Crymto you tried to exchange and adds a 10% fine. Buying Crymto costs 10% everywhere.

From your bug reports:
- **No more same-dock contraband profit.** Contraband could be bought and sold back in the same dock at a profit, because the smugglers' premium only applied to selling. The street price now carries the premium too, so buying always costs more than the same dock pays, and only a cargo run makes money.
- **B spends Crymto on contraband.** Contraband is paid for in Crymto first everywhere, then credits, without needing C.
- **Engineering training works when docked.** Opening engineering with 8 from the trade log, Money or another screen said training was only available while docked, even when you were.
- **Selling scooped or salvaged cargo no longer shows a false loss.** Cargo lost when your ship is destroyed, seized by customs, taken as a rescue fee or moved to a station bay used to leave its purchase cost behind, and the next free tonne of that good was charged for it. The cost now goes with the cargo (station bays keep it until you take the cargo back), and saves are cleaned up when loaded.
# 0.9.1 — fix: the game closed as soon as it went online

- **0.9.0 closed a few seconds after starting** for anyone playing online: the installer did not copy two new files that came with the living economy, and the game crashed when the first market update arrived. Updating installs them. If the game closes before you can accept the update, run `python3 ~/.local/share/star-trader/update.py` in a terminal.

# 0.9.0 — the living economy

The galaxy's economy now behaves like a real one, and it has a government.
- **Worlds change what they make.** Industries grow where their goods are scarce and dear and shrink in a glut, so a world that can't earn a living turns to something else. Prices come from what each world actually makes and uses, and populations grow with the traffic they get, so the galaxy gets busier as more commanders join.
- **Needs come in order.** People buy food and medicine first, then weapons for self-defence, clothes and their habits, then computers and machinery, and only then gold, silver and other luxuries. A poor world, or one where food is dear, cuts luxuries first.
- **The Galactic Council governs.** Every 6 hours it reviews every world. It sets a **trade tax** on every purchase and sale (shown in each exchange's header; lawless worlds pay none, struggling worlds pay less) and a galactic **interest rate** that steers spending and building. It funds station upkeep and police, licenses new industries, sends relief convoys, pays development grants to the weakest worlds, and builds **hyperspace beacons**: jumps to and from a beaconed world take 10% less fuel, shown on the Nav map.
- **Contraband follows demand and risk.** Smugglers don't avoid policed worlds; worlds pay them for the risk of bringing contraband in. Where customs and pirates take more cargo, contraband sells for more. Customs search harder where the Council funds more police, and less where it doesn't.
- **The news, from The Relay** ("News at the speed of the next jump"). The start screen carries the Council's latest decree, the main point of *The STA Tally* (the economy's daily figures from the Galactic Assay Office) and the latest Act of the STA, starting with *The Living Economy Act*. In game, new decrees and each day's Tally appear as news; a solar flare holds news from other worlds.

# 0.8.13 — steady prices, attack alarm and scoop fixes

From your requests:
- **Prices hold for the whole deal.** Pressing B (or S) again and again on the same cargo keeps the price you started at. The deal ends when you pick other cargo, switch between buying and selling, stop for 10 seconds or leave the station; then the price catches up with the market. Your own trades only ever move prices against you during a visit, so buying a load and selling it straight back can't make money.
- **Attack alarm.** A flashing red ALARM bar and a beep when a hostile ship or police are on you, you're under fire or taking damage, a mine is ahead, you're about to hit a rock, or you're overheating. X silences it until that danger is over; a new danger sounds again.
- **Scooping is announced** as a ship announcement, and the cockpit shows the nearest ore and what the scoops need: SLOW BELOW 50, CLOSE TO 260 m, HOLD FULL or COLLECTING.
- **The text cursor is a flashing solid block**, like an old terminal.

From your bug reports:
- **Y turns approach guidance on and off again** (0.8.10 had moved it to Ctrl+G only; Ctrl+G still works).
- **"Write a description first." no longer follows you back to the cockpit.** It now shows on the bug report screen only.
- The cockpit shows fine steering as ^F (it said I, its old key).

# 0.8.12 — screens numbered left to right

From your suggestions:
- **The top bar now runs 1 Nav, 2 VMS, 3 Money, 4 Menu, left to right, with each number on its button.** The number row matches: 0 home (the market when docked, the cockpit when flying), 1 Nav, 2 VMS, 3 Money, 4 Menu, 5 Comms, 6 trade log, 8 engineering, 9 help. Press the same number again to go back.
- **Bug reports and suggestions moved to Ctrl+0**, from anywhere. Menu (4), Report a bug still works.
- **Text boxes show a blinking cursor:** bug reports, notes, commander name and credit codes.
- Breakdown messages now point to Ctrl+E for a distress call (the old key was 6).

# 0.8.11 — fix: Flight controls button overlap

From your bug report:
- **The Flight controls button in the cockpit no longer overlaps the text beside it.** 0.8.10 gave it a stray "C" key hint (it has no key), which made it wider. Buttons without a key no longer show a hint anywhere.
- **The docking readout says "R radio"**, the new key for request docking, not "7 radio".

# 0.8.10 — new keyboard layout: numbers for screens, letters for actions

From your suggestion: every control now has a keyboard shortcut, laid out so it is easy to remember.
- **The number row opens screens, from anywhere:** 1 home (the market when docked, the cockpit when flying), 2 Nav, 3 VMS, 4 Money, 5 Comms (DSC console), 6 trade log, 8 engineering, 9 help, 0 feedback. Press the same number again to go back. Numbers never do anything else.
- **Letters are actions on the screen you're on, named for what they do.** In flight: D docking computer, R request docking, F look behind, L lay a mine, J jammer, Tab next target (K cloak, M missile, V laser, H jump, T cruise, O scoop and N hail are unchanged). In Money: B bank, X exchange, R redeem a code, F pay fines, J jobs, T trade log. Hails and job questions are answered with A, B, C (and Y to accept, P for payment in cargo).
- **Rarer flight controls use Ctrl:** Ctrl+S/P/R/U select the station, planet, rocks or sun beacon, Ctrl+F fine steering, Ctrl+G approach guidance, Ctrl+E distress call. Anywhere: Ctrl+N quick note, Ctrl+M full screen (no function keys needed).
- **Buttons show the new keys**, and the handbook (9) opens on a new Keys page listing what moved: Nav was G, VMS was X, Money was 9, Help was 1, docking computer was C, request docking was 7.

From your bug report:
- **The market notes no longer run under the Commander Status panel.** The solar-flare message was too long for the space; it's shorter now, and so is the outfitting hint.

# 0.8.9 — the economy breathes

Stations now have living economies, shared by every commander on the server.
- **People consume, workers produce.** Every planet's population needs basics (food, medicine), then comforts (textiles, computers, machinery) and, when they are doing well, luxuries (gold, silver, narcotics, arms). Factories turn out goods by economy: agricultural worlds make food, textiles and narcotics and need machinery; industrial worlds make machinery, computers, medicine and arms and need ore and food; frontier mining worlds make ore, gold and silver and need machinery and food.
- **Prosperity matters.** A well-supplied world becomes Thriving: its workers produce more and it buys more luxuries. Starve it and it slides to Struggling or Destitute and its factories slow. Populations slowly grow or shrink with prosperity.
- **Busy stations move faster.** The more ships trade at a station (commanders and bot freighters), the faster it consumes and produces, so the economy keeps up as more pilots join.
- **Gluts clear and shortages bite.** Dumped goods are slowly used up instead of staying cheap forever, and a world that makes nothing of something keeps needing it.
- **Galactic news.** Famines, plague outbreaks, mining booms, factory strikes, bumper harvests, festivals and local wars hit stations for 1–2½ hours and push prices hard. Every commander sees the same events. A solar flare blocks news from other systems.
- **See it in the market.** The stock column turns orange where a good is wanted and blue where there is a surplus, and a line under the market shows the population, how they are doing and how many ships are trading (or the running event). Planet profiles show what a world makes, its prosperity, what it wants and what it has spare.
- **Trading pays again.** Bot freighters used to haul any gap above 8%, so prices ended up nearly the same everywhere. They now only haul gaps of 60% or more, leaving the good routes to commanders.
- Routine trader and news messages no longer push an urgent warning off the screen.

Under the hood, each station is brought up to date in one step when someone looks at it, rather than ticking every station all the time. That is what an unlimited galaxy will need.

Server: update the server before (or with) this release. Older games still work with it; they just don't see the economy news.

# 0.8.8 — answer the update question first

- **The game waits for your answer when an update is out.** The start screen used to show the update offer as one line under the buttons, so you could click Online play and start without seeing it. Now the update question replaces the buttons: Update now (Enter or U) or Not now (N or Esc). Online play, Offline play and settings only appear once you have answered, and the game no longer auto-connects past it. Not now plays your current version and asks again next launch.
- `--offline` launches ask the same question in a window before the game opens, instead of only showing a desktop notification.

# 0.8.7 — a living galaxy: shared markets, traders, DSC distress calls and solar flares

From your bug reports:
- **BEST IN RANGE fills in when you arrive.** It used to list only systems the fuel left in your tank could reach, so straight after a jump every row showed "-". It now shows the best sale price within a full tank's reach, since you can refuel before leaving.
- **Every rock breaks, whatever laser you use.** Silver (and gold) rocks only broke with the mining laser selected. Now any laser cracks any rock; what's left to scoop depends on how gently it cuts: the mining laser leaves 3 pieces, pulse and beam 2, and the military laser smashes rocks fastest but vaporises most of the ore (0 or 1 piece).
- **Destroyed ships spill cargo.** Pirates drop plundered goods and police ships drop seized contraband, as well as disabled ships and traders. Fly slowly with scoops to collect it.
- **Disabled ships are no longer on every flight.** About one flight in three, a ship somewhere in the system (3.5–8 km away) calls for help a few minutes after you launch.
- **Fuel scoops checked.** They work: skim below 280 m altitude at speed 10–60 to refuel. The sun beacon hint now gives the same figure as the cockpit readout.

New:
- **One shared market.** Station stock is now held on the server, so every commander buys from and sells to the same stations; if Frank empties a station of computers, you'll find it empty too. Offline, the game carries on from the last stock it saw.
- **Supply and demand.** Prices follow stock: scarce goods cost up to 1.5x, gluts sell down to 0.75x. Stations slowly produce goods back to their normal level.
- **Bot traders.** Freighters buy goods where they are cheap and ship them to where they are dear, so stock moves around the galaxy. You will see them launch from the station and jump out, or jump in and fly to dock (white freighters on the scanner; 5 targets them). While docked, the market tells you when one arrives or leaves. Their cargo only reaches the other station if they make it: shoot one down and its cargo spills for you to scoop (100 cr fine in lawful systems).
- **DSC comms console** (450 cr, tech 3). Like a marine DSC radio, it receives distress alerts carrying the caller's identity, nature of distress (fire, hull breach, life support failure, drive failure) and position. Alerts repeat every minute until acknowledged. TAB opens the console; ENTER acknowledges and locks your direction marker on the vessel. Fire and hull breach crews don't last long: reach them in time or the alert stops with the vessel lost.
- **Any laser on the rear mount.** The rear pulse laser is now a rear laser mount (still comes with a pulse laser). In rear view (4), V moves any laser you own onto it; each bought laser sits on one mount at a time.
- **Solar flares.** Every so often (about once every two hours) a flare blacks out deep-space comms for 4–10 minutes: BEST IN RANGE turns to static, planet profiles show no prices for other systems, and the nav map stops showing other commanders. Local trading, docking, hailing, DSC and distress calls still work. Every commander sees the same flare at the same time.

Server: update the server before (or with) this release; it now holds the shared market (`PUT /v1/market`).

# 0.8.6 — the newest save wins

- **No more "Local and server saves differ".** When the copy on your computer and the copy on the server have both changed, the game now keeps whichever was played most recently and uploads or loads it automatically. The other copy is kept as a backup beside your save (`save.server-copy-…` or `save.before-restore-…`).
- **A dropped connection no longer stops syncing.** If the server saved your progress but the reply was lost, the game used to treat its next upload as a conflict and stop syncing for the rest of the session. It now picks up the server's revision and carries on.

# 0.8.5 — updates ask first

- **Updates ask first.** The game no longer installs a new release by itself. When one is out, the start screen says "Update vX.Y.Z is available · Enter: update now · Esc: play vCURRENT". Enter (or a click on that line) installs it, shows "Installing update… your saved game is kept" and restarts into the new version; Esc plays the current version and the game asks again next launch. A failed update is reported on the start screen and the current version stays playable (details in update.log). Works the same on Linux and macOS. With --offline, the game only notifies you that an update is available.

# 0.8.4 — fuel and course bearing fixes

From your bug reports:

- **Normal flight burns a quarter of the fuel it did.** Flying out past a station's 5,000 m mass lock and in from a hyperspace arrival used to cost about 1.4 units per trip; it now costs about 0.4. The launch check reserves enough for that flight as well as the jump, so it no longer passes you and then leaves you short.
- **You can fly toward a galaxy course.** The course arrow and target bearing now stay fixed in space, so turning toward them brings the course ahead. Before, the bearing turned with the ship and could never be reached.

# 0.8.3 — new community server

- The game now connects to the new community server at https://141-147-67-78.sslip.io. Paste your new invite code in Connection settings to join it.
- Accepting an invite starts a new commander on that server; it no longer copies in an offline pilot.

# 0.8.2 — clearer damage wording

- A damaged laser now shows LASER MALFUNCTIONING (and "LASER MALFUNCTION" when a shot misfires), so it is not confused with the signal jammer.

# 0.8.1 — disabled ships allow for stray fire

- Like stations, a disabled ship treats its first three hits as stray fire from a nearby fight: the crew radios "Cease fire!" with a count of hits left. A fourth hit within five minutes and they fire back. Quiet for five minutes and the count resets. They will still negotiate after stray hits.

# 0.8.0 — salvage, negotiation and battle damage

- **Hail disabled ships (N).** Offer to restart a stranded ship's drive with one unit of your fuel and name your price: 50, 120 or 250 cr. The crew accepts what they can afford (more when their hull is failing), counters with their limit, and stops talking if you push too hard. They can pay in cargo instead.
- **Or take it by force.** A destroyed disabled ship spills 2–4 cargo canisters your scoops collect, but a lawful station fines you for attacking a helpless vessel.
- **Disabled ships fight back.** Fire on one and its crew swings what thrust it has left to return fire; the more damaged it is, the worse it aims.
- **Battle damage.** Your ship turns more slowly as the hull weakens (down to 40% at zero), and damaged systems fail intermittently: scanner faults below 60% hull, target bearing offline below 45%, laser jams below 30%. Station repairs fix everything.

# 0.7.1 — name your commander on the welcome screen

- New pilots type their commander name on the first welcome page, with a reminder that it can be changed any time under Menu, Commander name.

# 0.7.0 — your bug reports and suggestions

Everything here came from in-game reports.

- **Visible combat.** Ships, asteroids and missiles explode on screen. Missiles fly to their target. The cockpit shows the target's shield and hull.
- **Disabled ships can be destroyed** with lasers (a 100 cr fine at lawful stations for attacking a helpless vessel).
- **Mining feedback.** Each mining-laser hit reports progress; other lasers explain that only a mining laser breaks rock.
- **Gold and silver.** New commodities, scarce at stations, and found in rare GOLD ROCK and SILVER ROCK asteroids that take more cutting. Scoops collect the metal automatically.
- **A real fuel market.** Fuel costs 7–14 cr per unit depending on the system, and stations buy it back (VMS, K). Skim a sun for free fuel and sell it. A short wallet still buys whatever whole units it can.
- **Station mass lock.** Hyperspace needs 5,000 m clearance from a station, and jumps now arrive outside the patrol zone, where pirates can be waiting.
- **Best sale in range.** The market shows the top sale price for each commodity at systems your fuel can reach.

Older saves gain the new commodity slots automatically, and the server accepts saves from both older and newer versions.

# 0.6.4 — trade log and sun-skimming readout

- **Trade log** in Money (6): your last 60 trades with time, station, price and the profit on each sale. Viewable anywhere, docked or in flight.
- **Sun skimming readout:** near the sun the heat panel shows your altitude above the surface and whether your fuel scoops are collecting, or why not.
- **Automatic ore pickup:** fitted scoops collect ore fragments when you fly slowly within 260 m.

# 0.6.3 — game introduction

- New pilots get a four-page introduction: who you are, the point of the game, how to play, and how to send bug reports and suggestions. Reopen it any time from Menu, Introduction.

# 0.6.2 — fallback server addresses

- Online play tries each address in `fallback_servers` (Connection settings file) when the main server address does not answer, so a host's home-network name keeps working when the public link is down.

# 0.6.1 — online settings that work from anywhere

- New installs point at the community server's public address (https://kentons-imac.tail8cde7d.ts.net), so online play works away from the host's home network.
- The new-pilot screen has a Paste invite button (Ctrl+V works too), so players with an invite code are set up in one click.

# 0.6.0 — Mac install with nothing else needed

- **One-line Mac install on a brand-new Mac.** No Xcode tools, git, Homebrew or Python needed:
  `curl -fsSL https://raw.githubusercontent.com/womb4t/star-trader/main/install-mac.sh | bash`
  The app carries its own Python 3.12 (Intel or Apple Silicon), SDL2 and SDL2_ttf, and the Mac's trusted certificates for online play. It opens from Launchpad with its own Dock name and icon.
- **Updates no longer need git.** Installs that did not come from a Git checkout update from the release download.
- Tested on a stock-configured Intel Mac (no system Python or git on PATH): installs, launches, loads SDL from inside the app, connects over HTTPS, nothing quarantined.

Already have Star Trader on a Mac? Run the one-liner above once to switch to the self-contained app; saves are kept.

# 0.5.1 — Mac launch fix for Apple's Python

- Fix the Mac app crashing at launch when the installer used Apple's Command Line Tools Python (common on new Macs): its library link is now repointed after copying, and the installer checks that the bundled interpreter really starts, falling back to launching Python directly if not.

If Star Trader would not open on your Mac, run this once in Terminal:

```bash
cd "$HOME/star-trader" && git pull --ff-only && bash install-mac.sh
```

# 0.5.0 — shared universe preview, Mac support, law and order

- **See other pilots online.** Players on the same server see each other's ships, names and radar contacts in every system. This is an early preview: no combat, trading or collisions between players yet, and positions are reported by each game, not checked by the server.
- **Sign up in the game.** New pilots choose a name (and may give an email for game news) right from the Online play screen. Hosts can also send one-paste invite codes. Fresh installs point at the community server, and returning online players reconnect automatically.
- **macOS installer.** `install-mac.sh` sets up the official SDL frameworks and adds Star Trader to Applications with its own icon. Intel and Apple Silicon, no Homebrew needed.
- **Automatic updates.** New releases install themselves when the game starts. Saves are preserved.
- **Commander status.** Your name, rank (Newbie to Legend, earned from kills, trading profit and hyperspace jumps) and a 0–5 wanted level on the station screen.
- **Law and order.** A few stray shots at a station bring a call from station control and a fine instead of police. Lawful stations hold your launch until fines are paid. Wanted pilots can surrender and dock to be arrested; destroying police earns prison time (one real hour per day, up to seven), with daily work shifts or a 1-in-10 bribe to escape.
- **Patrol zones.** Pirates do not attack within 5,000 m of a lawful station.
- **Bug reports and suggestions** are logged in the game and sent to the developers when you are online. GitHub drafts are gone.
- **Quality of life.** Backspace is Back on every screen. Bank presets of 50/100/1000 cr plus a custom amount. Blinking cursor in Connection settings.
- **New star system names** (Halvora, Corvant, Meridel, Brennix, Skarrow, Velmora, Duskholt, Ambrell). Saves migrate automatically.
- **Fixes.** Python 3.9–3.11 compatibility, online saves survive a server address change, and the commander name shows when playing online.

# 0.2.26 — clear mine and missile availability

- Stop ammunition counts hiding technology restrictions in the outfitter.
- Show selected equipment requirements and local technology, with a visible failure announcement.
- Mines remain 75 credits at tech 4+, maximum four aboard.

# 0.2.25 — clipboard code entry and separate heat instrument

- Add Ctrl+V/C/X/A clipboard editing for codes, Notes and feedback.
- Add Paste, Copy and Select all buttons to code redemption, with visible selection.
- Separate heat from fuel: dedicated cockpit thermal gauge, shield readout and danger marker.
- Exercise native SDL clipboard access, Ctrl+V event routing and code redemption at four window sizes.

# 0.2.24 — Nav order and cleaner bottom action bars

- Rename the top navigation item to Nav and place it before VMS.
- Replace oversized footer buttons with compact, consistently spaced actions and separate shortcut badges.
- Align Return/Cancel actions to the right and wrap crowded toolbars safely.
- Preserve cockpit course information alongside the flight control button.

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
