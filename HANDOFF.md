# Star Trader — iMac handoff

Kenton wants to use this iMac as the first private progress server for the Omarchy Python game at https://github.com/womb4t/star-trader.

Read SERVER.md before setup. v0.3.0 adds a headless Python/SQLite save server and optional client save synchronisation. This is progress persistence, not yet a shared multiplayer simulation. Keep all eight systems and a maximum of eight tester accounts. Future shared combat, piracy/trading, fleets, player police and bases are planned in MULTIPLAYER.md and ROADMAP.md.

On this iMac, inspect Python (3.9+) and Git, clone/update this repository under ~/star-trader, create the Kenton account if it does not already exist, and start the server for the trusted home LAN. Keep credentials outside the repository. Do not print the token into chat or upload it. Identify the real LAN address and help transfer the token file privately to the laptop. Do not open router ports. Ask before making unrelated macOS system changes. Do not run the Omarchy installer on macOS; the server needs no game graphics.

The laptop source checkout is /home/kenton/Documents/Codex/2026-10-16/coul/outputs/star-trader. Installed game: /home/kenton/.local/share/star-trader/star_trader.py. Always give Kenton full Bash commands usable from a fresh terminal. The standard game launcher remains offline; server play uses explicit --server, --token-file and --allow-lan options. Preserve existing saves. SERVER.md gives import, offline fallback, conflict recovery and backup instructions.

This file is project context for another Codex chat, not a live transfer of the original session. Follow Kenton's latest instructions in the new chat.
