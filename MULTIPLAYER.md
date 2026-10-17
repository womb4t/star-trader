# Self-hosted universe roadmap

Status: design only. The current release is a fully offline single-player game with robot pirates. It opens no network connections and does not yet support fleets, chat, player police, transfers or bases.

## Intended experience

A host runs a persistent universe on their own computer or server. Players join that universe using its address. There is no mandatory central service. The same game continues to work offline.

Players may trade, mine, pirate, protect convoys, or combine those activities. Roles are activities and reputations rather than permanent character classes. Galactic police are an earned, server-managed jurisdiction with responsibilities, not an unlimited admin power.

Robot traders, pirates and police should keep a universe active even when few people are online. New players should be able to learn and earn money before entering dangerous space.

## Server owns the rules

The server must own credits, accounts, inventories, market stock, ship modules, damage, ammunition, mining yield, bases, legal status and persistent ownership. Clients send intentions such as “buy one tonne”, “fire”, or “transfer 50 credits”; clients never submit an authoritative balance or bounty.

Offline saves remain separate from server characters. A normal client cannot import its offline credits or equipment into a competitive universe. A host may explicitly create a sandbox universe with different import rules.

Use a fixed simulation tick, unique entity IDs and ordered commands. Validate movement, range, cooldown, ammunition and line of fire on the server. Replicate nearby entities and reconcile client prediction. Use versioned messages, authenticated sessions, rate limits, and encrypted connections for Internet deployments. Store tokens securely and never log them.

Markets, credit transfers and module fitting require atomic transactions. Every transfer needs a unique request ID so a retry cannot pay twice. Invalid or unaffordable actions leave both accounts unchanged. Saves need versioned migrations, backups and crash recovery.

## Ship fitting within constraints

Turn the existing equipment catalogue into a shared, versioned ruleset. Each hull defines hardpoints, module slots, cargo mass, power output and heat limits. A module declares cost, technology requirement, slot type/size, mass, power draw and heat output. All builds must satisfy every constraint; cargo cannot be squeezed out of a full ship by fitting an upgrade.

Players can customise builds using server-approved modules and cosmetics. They cannot submit executable Python or arbitrary module statistics. Hosts may add declarative modules with validated IDs and bounded values; clients receive the ruleset identifier and display data. Unsupported rule versions should fail clearly.

The current catalogue and Pilot economy methods are a useful starting point. Flight, combat and transactions still need extraction into a deterministic simulation before networking; the current local collision/combat implementation is not an authoritative network engine.

## Fleets and communication

Fleets have invitations, membership, named ranks, explicitly assigned permissions and shared navigation markers. Fleet leaders do not automatically gain access to members’ personal credits or ships. Add fleet storage and a treasury only with separate deposit/withdraw permissions and audit history.

Provide local-system, fleet and direct text chat, with mute/block controls, host moderation and rate limits. Do not treat chat text as commands. Add a transfer screen that identifies the recipient and amount before submission; show a receipt to both parties and keep an audit record on the server.

## Pirates, traders and police

Attacking a clean ship, theft and unlawful destruction affect legal status in the jurisdiction where they occur. Bounties are issued and paid by server rules, with protection against repeatedly farming an accomplice. Provide visible combat-zone and security indicators.

Player police need eligibility, jurisdiction, revocable warrants, permitted actions and an accountable record. A badge must not permit arbitrary credit seizure, unrestricted player damage, or administration. Distinguish legitimate self-defence, consensual combat and piracy. Hosts choose the security policy; the client presents it before joining.

Decide and test death, insurance, cargo recovery and combat-disconnect rules before enabling competitive combat. Safe spawn/station zones and stronger NPC security can protect beginners while frontier systems retain risk.

## Player bases

Begin with one deployable outpost type. Construction consumes server-verified credits and materials, requires a permitted location, and creates persistent ownership. Require minimum distances from stations and other claims, plus per-account and per-system limits.

Add docking/storage permissions, upkeep, production, fleet ownership and trade in stages. Before enabling destruction, define offline protection, siege windows, asset recovery and host moderation. Bases must not create unlimited free goods, block public routes or erase another player's possessions through a client request.

## Delivery stages and acceptance checks

1. **Strengthen offline simulation:** separate rules from rendering, version saves, add seeded entities, introduce NPC traders and police, and keep regression tests for trade, fitting, docking and mining.
2. **Private cooperative server:** persistent accounts, authentication, shared markets, visible ships and server-authoritative simulation. Check two clients, reconnects, latency, duplicate commands and a server restart without duplication or loss.
3. **Competitive economy/combat:** weapons, piracy, policing, reputation, death/insurance and host policies. Test forged commands, simultaneous purchases, disconnects under attack and bounty abuse.
4. **Social systems:** fleets, communication and atomic player credit transfers. Check permissions, retries, insufficient funds, mute/block and moderation.
5. **Persistent construction:** claims, base building, storage and ownership. Check overlapping claims, concurrent withdrawals, upkeep, crash recovery and offline protections before adding sieges.

A host should eventually have documented setup, backups, restore/export, moderation, ruleset configuration and update/migration tools. Hosting on the public Internet will require explicit network/firewall setup by the host; the game should never open router ports automatically.


## Owner economy and station development — requested future features

These are recorded plans, not current capabilities:

- **Storage-centre ownership:** players can purchase a centre or a group of bays, set rental prices and terms, collect rent, and manage tenant access with an auditable ledger. The current release only supports personal storage rented from or bought at NPC stations.
- **Off-plan bay sales:** developers can fund a new station by selling future storage capacity before construction completes. Specify the proposed location, build milestones, completion conditions, buyer claims, escrow, refunds and treatment of project failure before taking money. Do not mint usable bays until the relevant construction phase is complete.
- **Personal bases and stations:** buying, renting, constructing and, under explicit server rules, capturing or stealing a base. Separate ownership of a building from ownership of tenants' goods and financial deposits; a capture must not silently convert all tenant assets into attacker property.
- **Armed installations:** hardpoints, ammunition, power/heat budgets, defensive AI, security permissions, docking policies and maintenance. Station defences must obey the server's legal and combat rules.
- **Owner fleets:** personal/fleet ships, officers or robot captains, orders, escort/patrol/trade assignments, shared navigation, docking/repair facilities and operating costs. Membership and command permissions must be explicit.
- **Fleet-funded expansion:** rent, trade revenue and off-plan sales may fund additional bays, defence modules, shipyards and later construction stages, with server-side conservation of credits/materials.

This scope should be staged after reliable persistence, ownership, bank transactions and authoritative combat. Define tenant protection, offline raids, sieges, insurance and host moderation before enabling destructive base capture.

## Disconnects and uncaptained ships — future server rule

The universe server keeps a disconnected player's ship as the same persistent entity. It continues its actual trajectory, autonomous orders, fuel/heat use, combat, collisions and damage. Logging out does not grant invulnerability, teleport to a station, unload cargo or remove a bounty.

Reconnect attaches the authenticated player to the existing surviving ship. If it was destroyed, present that recorded outcome and the recovery/insurance choices; do not restore a pre-combat client snapshot. Crewless ships can still be rescued, salvaged, boarded or destroyed under explicit universe policy. A server shutdown checkpoints the universe, distinct from a player disconnect. Test repeated reconnects, duplicate settlement requests, deliberate client termination and server crashes.

The offline game's bounded catch-up and emergency salvage are a local approximation, not a multiplayer simulation or a substitute for an always-running authoritative server.
