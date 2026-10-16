# Next offline expansion

These are planned features, not claims about the current release. Finish and stabilise 0.2.0 before expanding the game further. Working names below give the next systems their own identity.

1. **Seeded star atlas:** deterministic sectors, hundreds of generated systems, persistent coordinates, searchable descriptions and distinct local economies. Expand beyond the current eight planets; consider multiple sectors linked by a rare single-use “Fold key”. Keep old saves and routes migratable.
2. **Orbit Wardens:** more complete police and legal rules, security levels, self-defence and reputation. Expand current customs/fines into justified pursuits and bounty work. A clean trader should not be treated as a criminal for defending against pirates.
3. **Living traffic:** varied robot freighters, escorts, miners, raiders and bounty hunters with different hulls, equipment and behaviour. Allow piracy and salvage, with legal consequences. Introduce “Riftborn” alien encounters and rare interrupted jumps.
4. **Tactical scope:** a readable local scanner, front/aft contacts, range and identification. Expand the existing rear view and rear pulse laser with side views and additional weapon mounts so a contact behind the ship is more than a warning message.
5. **Ship energy and damage:** separate fore/aft shields, energy reserves, weapon heat, equipment damage and actual enemy missile entities. Add a “Pulse scrubber” anti-missile countermeasure distinct from 0.2.0's signal jammer.
6. **Rescue and last-resort equipment:** a “Drift capsule” with explicit insurance/cargo-loss rules, and a single-use “Nullburst charge” with consequences for neutral ships. Keep blast effects bounded and visible.
7. **Career and contracts:** combat standing, delivery/escort/bounty jobs, progression and occasional authored missions. Start with a small number of robust mission types rather than a large brittle quest chain.
8. **Audio and presentation:** original sound cues for targeting, incoming threats, docking and travel; volume/mute controls; no copied music or original game assets.

Build these around a deterministic simulation, stable entity IDs, versioned ship/module definitions and save migrations. Those are also prerequisites for the separate self-hosted multiplayer plan in [MULTIPLAYER.md](MULTIPLAYER.md).

## Later self-hosted universe

Players may be traders, miners, pirates, police, or combine activities; hosts choose universe policy. Planned fleets, communication, credit transfers, constrained ship customisation and player bases require authoritative server rules and persistence. See [MULTIPLAYER.md](MULTIPLAYER.md) for stages, permissions and acceptance checks. None of these networking features is enabled in 0.2.0.
