# Private progress server (v0.4.0)

The iMac stores separate progress for up to eight testers. All eight star systems remain available. The game still runs on each laptop, with robot ships and offline flight. This release synchronises saves; it does **not** make players visible to one another or share combat, markets or credits. The client is trusted to supply its own progress, so this is not yet a competitive multiplayer economy.

The server needs Python 3.9 or later and uses only the Python standard library, including SQLite. It does not need SDL, graphics, pip packages or the Omarchy installer. Keep the iMac awake and connected while playing. Stop the server with Ctrl+C. There is no router configuration or automatic port forwarding.

## First setup on the iMac

In a fresh macOS Terminal:

```bash
cd "$HOME" &&
git clone https://github.com/womb4t/star-trader.git &&
cd "$HOME/star-trader" &&
python3 --version &&
python3 save_server.py create-player Kenton --token-file "$HOME/.star-trader-server/kenton.token" &&
python3 save_server.py serve --host 0.0.0.0 --port 8765 --lan
```

If the checkout already exists, use this instead (creates the player only if its token file is absent):

```bash
cd "$HOME/star-trader" &&
git pull --ff-only &&
python3 --version &&
if [ ! -f "$HOME/.star-trader-server/kenton.token" ]; then
  python3 save_server.py create-player Kenton --token-file "$HOME/.star-trader-server/kenton.token"
fi &&
python3 save_server.py serve --host 0.0.0.0 --port 8765 --lan
```

If Python or Git is absent, install it before running these commands. macOS may offer to install command line tools for Git. If macOS asks whether Python may accept incoming connections, allow access on your home network. In System Settings, find the iMac's current network IP address. Use that address below, for example `192.168.1.20`; do not use that example unless it is your iMac's address. A DHCP reservation in your router can keep the address stable.

The database is `~/.star-trader-server/progress.sqlite3`. The player token is a secret login credential. Transfer the **file** `~/.star-trader-server/kenton.token` privately to `~/.config/star-trader/kenton.token` on the laptop, and run `chmod 600 ~/.config/star-trader/kenton.token` there. Do not put tokens, databases or saves into GitHub, screenshots or public chats. Each tester gets a separate account and token:

```bash
cd "$HOME/star-trader" &&
python3 save_server.py create-player Tester2 --token-file "$HOME/.star-trader-server/tester2.token"
```

## Connect the Omarchy laptop

Close the game first. This fresh-terminal command asks for the real iMac address and privately transferred token file. It imports your existing offline save only when this server account has no progress yet; the original offline save remains untouched.

```bash
cd /home/kenton/Documents/Codex/2026-10-16/coul/outputs/star-trader &&
git pull --ff-only &&
bash install.sh &&
read -r -p "iMac local IP address: " star_server_ip &&
read -r -p "Path to your private token file: " star_token_path &&
python3 /home/kenton/.local/share/star-trader/star_trader.py \
  --server "http://${star_server_ip}:8765" \
  --token-file "$star_token_path" --allow-lan --import-local-save
```

Use the same launch command on later visits; `--import-local-save` does not replace an existing server save. The single Star Trader app launcher offers Online play and Offline play. Configure the server address and token-file path with Connection settings; existing Star Trader Online settings are migrated automatically. Server saves are cached under `~/.local/share/star-trader/servers/<account-id>/save.json`. The Menu shows connection/save status. Saves upload in the background at most every five seconds and once on exit. Your local checkpoint is written first.

If the iMac is temporarily unavailable, append `--offline-if-unavailable` to the server launch command. This works only with an existing local server save and its revision metadata. Reconnection uploads your unsynced progress unless another computer has changed the server copy. This explicitly chosen offline mode keeps the same account's local slot; it does not mix in your ordinary offline pilot.

If two computers play the same account, revision conflicts stop uploads and preserve the local save. Quit both games and decide which copy to keep. To deliberately load the server copy, append `--restore-server-save`; the local save is backed up as `save.before-restore-<timestamp>.json` before replacement. There is no automatic merging or silent overwrite. A server-rejected save stays local; consult the Menu status and server terminal.

## Start the iMac server again

```bash
cd "$HOME/star-trader" &&
python3 save_server.py serve --host 0.0.0.0 --port 8765 --lan
```

For testing on this home network, `--lan` permits unencrypted HTTP. Anyone who obtains a token can access that account. Keep this on a trusted private network; do not forward port 8765 to the Internet. For testers elsewhere, plan a private VPN or an HTTPS reverse proxy before opening access. The built-in server supports `--cert CERT.pem --key KEY.pem` for HTTPS. Client HTTPS connections verify certificates; redirects are refused to protect tokens.

## Back up and restore

A backup command uses SQLite's consistent backup API and is safe while the server runs:

```bash
cd "$HOME/star-trader" &&
python3 save_server.py backup "$HOME/star-trader-progress-$(date +%Y%m%d-%H%M%S).sqlite3"
```

Keep backups somewhere other than the iMac as well. The database stores token hashes, current saves, revisions and the most recent 20 revisions per player. To restore an entire backup: stop the server, move its current database **and any matching `-wal`/`-shm` files** aside, copy the chosen backup to `~/.star-trader-server/progress.sqlite3`, and restart. Retain the moved files until recovery is checked. Existing player token files still work with the matching backup; reconnecting clients may need the explicit restore option after a rollback. Never copy just the active database file while the server is running.

Updates: stop the server, make a backup, then run `cd "$HOME/star-trader" && git pull --ff-only` and restart it. Update clients too. The server does not change your macOS settings or run as a background service yet.
