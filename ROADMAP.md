# Next offline expansion

These are planned features, not claims about the current release. The current release is 0.4.0; stabilise existing gameplay and private save synchronisation before expanding the game further. Working names below give the next systems their own identity.

1. **Seeded star atlas:** deterministic sectors, hundreds of generated systems, persistent coordinates, searchable descriptions and distinct local economies. Expand beyond the current eight planets; consider multiple sectors linked by a rare single-use “Fold key”. Keep old saves and routes migratable.
2. **Orbit Wardens:** more complete police and legal rules, security levels, self-defence and reputation. Expand current customs/fines into justified pursuits and bounty work. A clean trader should not be treated as a criminal for defending against pirates.
3. **Living traffic:** varied robot freighters, escorts, miners, raiders and bounty hunters with different hulls, equipment and behaviour. Allow piracy and salvage, with legal consequences. Introduce “Riftborn” alien encounters and rare interrupted jumps.
4. **Tactical scope:** expanded filtering and identification for the existing clickable local scanner. Expand the existing rear view and rear pulse laser with side views and additional weapon mounts so a contact behind the ship is more than a warning message.
5. **Ship energy and damage:** separate fore/aft shields, energy reserves, weapon heat, equipment damage and actual enemy missile entities. Add a “Pulse scrubber” anti-missile countermeasure distinct from 0.2.0's signal jammer.
6. **Rescue and last-resort equipment:** a “Drift capsule” with explicit insurance/cargo-loss rules, and a single-use “Nullburst charge” with consequences for neutral ships. Keep blast effects bounded and visible.
7. **Career and contracts:** combat standing, delivery/escort/bounty jobs, progression and occasional authored missions. Start with a small number of robust mission types rather than a large brittle quest chain.
8. **Audio and presentation:** original sound cues for targeting, incoming threats, docking and travel; volume/mute controls; no copied music or original game assets.

Build these around a deterministic simulation, stable entity IDs, versioned ship/module definitions and save migrations. Those are also prerequisites for the separate self-hosted multiplayer plan in [MULTIPLAYER.md](MULTIPLAYER.md).

## Later self-hosted universe

Players may be traders, miners, pirates, police, or combine activities; hosts choose universe policy. Planned fleets, communication, credit transfers, constrained ship customisation and player bases require authoritative server rules and persistence. See [MULTIPLAYER.md](MULTIPLAYER.md) for stages, permissions and acceptance checks. Private account save synchronisation is available; the shared simulation and social features below remain future work.


## Requested owner/fleet economy (future)

Add purchasable storage centres with player-set bay rentals, followed by off-plan bay sales to fund station construction. Later add personal bases, armed defences, owned/robot-crewed fleets and shipyards. Whole installations may eventually be bought, rented or captured under server rules. Protect tenant property and define escrow, refunds, construction failures, maintenance, command permissions and siege/offline rules first. Details and the uncaptained-ship disconnect rule are recorded in [MULTIPLAYER.md](MULTIPLAYER.md).

## Insurance, assistance, lending and player bounties (future)

Requested for future releases; none is implemented by this roadmap change:

- **Insurance:** purchasable cover for ships, fitted equipment, cargo and/or bases, with explicit premiums, excess, limits, exclusions and claims/replacement rules.
- **Breakdown/support cover:** a paid assistance package for towing, emergency fuel and repairs, with coverage areas, call-out limits and the effect on salvage charges clearly defined.
- **Player lending:** players can offer another player a loan with an agreed interest rate or fixed fee. A central in-game system records the contract and recoups repayments automatically under agreed rules.
- **Player-posted bounties:** players can fund and place a bounty on a named player, with server-verified completion and payment.

Details and open design decisions are recorded in [MULTIPLAYER.md](MULTIPLAYER.md). Those game contracts use in-game credits; the separately proposed real-money exchange is described below.

## Universal asset sales and StarTraderEx credit exchange (future)

Requested for future releases; planning only:

- **Sell owned assets:** support selling anything the player owns, including ships, fitted/spare equipment, cargo, storage bays/centres, bases and fleet assets. Define ownership transfer, contents, outstanding commitments and what happens if the last ship is sold.
- **Buy credits with real money:** let players purchase credits using real-world money and add the settled purchase to their in-game balance.
- **Earn and sell credits:** let players offer eligible earned credits for sale through a marketplace and receive real-money proceeds from completed sales.
- **StarTraderEx commission:** StarTraderEx takes a commission on marketplace transactions. The rate, fee basis, pricing mechanism and payout terms remain to be decided and shown before commitment.

See [MULTIPLAYER.md](MULTIPLAYER.md) for the recorded exchange design questions. No real-money purchase, credit redemption, payout or asset marketplace is currently enabled.

## Planet messages and local notices (future)

- Let players leave messages at a planet or station for named individual players, with recipient identity, delivery and privacy rules.
- Add local wanted and for-sale noticeboards, with searchable listings, expiry and moderation. Clarify whether a wanted notice is advertising, a bounty contract or an official police warrant.
- Link listings to the future asset marketplace and bounty system; posting a notice alone must not transfer ownership, credits or criminal status.
- Keep planet profiles as the entry point for local information and these future communication features. No messaging or player notices are enabled in this release.

## Commander and ship scanner (future)

Requested 22 October 2026. Let pilots scan for other commanders and ships within a radius:

- A scanner mode listing every ship in range (other commanders, pirates, police, traders, disabled ships) with commander name, ship type, distance and bearing, nearest first.
- Range depends on equipment: a short standard range, extended by a purchasable long-range scanner module; cloaked ships stay hidden or show only as an unidentified contact.
- Search by commander name to find a friend (or a target) in the current system; select a result to set a navigation marker.
- Online, the server decides who is in range from authoritative positions, so a modified client cannot reveal everyone in the galaxy. Respect privacy: a pilot could choose to fly "dark" (no name broadcast) at the cost of looking suspicious to police.
- Later: wanted levels and bounties shown on scan results, so bounty hunters can find wanted commanders.
- **Deployable watch beacons (tripwires).** Drop a small device in space, set to watch for chosen commander names, ship types or wanted levels within its radius. When something matching passes, it sends a deep space message to its owner (wherever they are, delivered next time they are online if not). Questions to settle before building: purchase cost and limits per pilot, battery life or expiry, whether other pilots can detect, destroy or salvage a beacon, a minimum spacing from stations and routes, and false-alarm and spam limits on messages. Online, the server owns beacons and does the matching.

## Multiplayer test scope

Keep all eight current systems and travel between stations, with the existing ship/equipment selection. Initial target: up to eight connected testers on a persistent authoritative server. Include cross-system trading, fuel, travel, docking and combat in the first playable test; do not lock everyone to one system. Offline play remains available.
