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

## Insurance, support plans, player loans and bounties — future requests

These insurance, support, lending and bounty features are future in-game services. A separate proposed real-money credit exchange is recorded below; none of these services is currently enabled.

### Insurance

Allow players to purchase policies covering selected ship hulls, equipment, cargo and possibly bases. Display premiums, excess/deductible, insured value, limits, exclusions, term and renewal before purchase. Specify how destruction, theft, piracy, unattended ships and base capture affect claims. Server-verified losses create one claim/settlement; reconnecting or retrying must not create duplicate payouts. Recovery can be replacement equipment or credits under the chosen policy.

### Breakdown and support packages

Offer paid breakdown-style assistance covering some combination of towing, emergency fuel, field repairs and recovery. Define station/frontier coverage, call-out limits, waiting periods, response times and exclusions. Explain whether the package replaces, reduces or leaves part of the existing salvage claim. Support cover must not grant combat invulnerability or silently extract a ship from combat without server rules. Offline robot assistance can precede player-provided services.

### Player-to-player loans with central collection

A lender offers principal in in-game credits, with either an agreed interest rate or a fixed fee. The borrower explicitly accepts the quoted total/repayment schedule and collection terms. A central, server-authoritative ledger disburses the principal once, records the debt, and recoups payments automatically from the agreed funds/income sources. Repayments credit the lender atomically and produce receipts for both parties.

Before implementation, decide: simple versus compound interest; rate periods; instalments/due dates; early repayment; collection priority relative to fines/rent; which wallet, bank balances or future income may be used; protected minimum balances; caps; collateral if any; default/insolvency; and treatment of death, offline periods, account deletion and universe resets. None of those choices should be implied by a client or imposed after acceptance. Retry/disconnect tests must prove that loans cannot duplicate principal, collect twice, or erase debt. Hosts may configure permitted terms and moderation rules.

### Player-funded bounties

Allow a player to place a bounty on another named player by depositing the offered reward into central escrow. Record issuer, target identity, amount, qualifying outcome, jurisdiction, expiry, cancellation/refund rules and who may claim. Distinguish a private contract from a lawful police warrant: posting a bounty does not automatically make the target a criminal. Define whether a contract requires destruction, capture or another verified outcome.

Only the server can verify completion and release the reward once. Define rules for self-claims, alternate accounts, collusive farming, repeat targeting, friendly-fire and safe zones, together with host moderation and target visibility. These choices belong alongside piracy/policing policy before enabling the feature.

## Universal asset sales and StarTraderEx — proposed future marketplace

### Selling anything the player owns

Support selling player-owned ships, installed/spare modules, ammunition, cargo, storage bays, storage centres, bases/stations and fleet assets. Define NPC buyback versus player listings, pricing, condition and included contents. A ship/base listing must disclose what equipment, cargo, rental contracts or other commitments transfer with it. Prevent simultaneous use, duplicate listings, double sales, and sales of assets not legally transferable under the universe rules. Consider loans/collateral, fleet co-ownership, tenants and captured/stolen assets explicitly. Selling the last ship must leave the pilot in a valid station/transport state rather than creating an automatic replacement that can be sold repeatedly.

### Real-money purchases and player credit sales

The requested commercial model is:

1. A player buys credits with real-world money; a settled purchase adds credits to their in-game money.
2. Players earn credits in the game and may list eligible credits for sale through the marketplace.
3. A completed sale pays the seller real-money proceeds, with **StarTraderEx taking a commission**.

This is a proposal, not an enabled purchase/redemption service or a promise of a fixed credit value. Commission rates, exchange pricing (fixed price/order book/listings), supported currencies/regions, payment methods, minimums, settlement timing and payout terms have not been chosen. Show gross price, commission and net proceeds before either party commits.

### Decisions before implementation

- Keep an authoritative, auditable ledger for purchases, earned credits, reservations, transfers, refunds, sales, commission and seller payouts. Reserve listed credits so they cannot also be spent, lent or withdrawn; retrying an operation must not duplicate credits or money.
- Define which purchased/earned credits are eligible for resale, provenance tracking, payout eligibility, and treatment of reversals, disputed payments and fraud. Decide how insurance claims, loans, bounties and asset sales interact with exchange eligibility.
- Decide how the commercial exchange relates to independently hosted universes. A host's ability to edit saves or mint arbitrary game credits must not automatically create credits eligible for central real-money sale; trusted-universe eligibility and cross-universe transfers require an explicit policy.
- Define payment-provider, identity, age, jurisdiction, tax/reporting, customer-support and dispute requirements through a dedicated commercial review before enabling real-money operations. These are open planning tasks, not conclusions about any particular legal classification.
- Evaluate economic balance and abuse controls before connecting earned credits, uncaptained-ship losses, lending, bounties, player property and real-money payouts. Test settlement failures, account compromises, duplicate requests and recovery from interrupted transactions.

Current releases remain offline games with game-only balances. They do not accept payments, redeem credits, pay sellers or collect commission. Record and implement this work as a separately reviewed future service.
