# Hosting the Star Trader server

The server is packaged as a container, so it runs the same on any Linux machine with Docker: a cloud VM (for example Oracle Cloud's Always Free tier), a home server or a NAS. `docker-compose.yml` runs two containers:

- **server**: the Star Trader progress server (Python standard library only). Saves live in the `star-trader-data` volume.
- **https**: [Caddy](https://caddyserver.com), which gets and renews a free HTTPS certificate and forwards players to the server.

## 1. Prepare the machine

You need Docker with the Compose plugin, ports **80 and 443** open to the internet, and a name that points at the machine's public IP address:

- your own domain (an `A` record such as `play.example.com`), or
- a free name from [sslip.io](https://sslip.io) that needs no setup: for IP `203.0.113.7`, use `203-0-113-7.sslip.io`.

On Oracle Cloud, also allow ports 80 and 443 in the instance's VCN security list. Ubuntu images there block them in the firewall too: `sudo iptables -I INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT`, then save the rules with `sudo netfilter-persistent save`.

## 2. Start it

```bash
git clone https://github.com/womb4t/star-trader.git && cd star-trader &&
STAR_TRADER_DOMAIN=203-0-113-7.sslip.io docker compose up -d --build &&
curl https://203-0-113-7.sslip.io/health
```

Put the variables in a `.env` file next to `docker-compose.yml` so they persist:

```
STAR_TRADER_DOMAIN=203-0-113-7.sslip.io
STAR_TRADER_SIGNUP=off
```

`STAR_TRADER_SIGNUP` is `off` by default (players join with invite codes), or `open` to let anyone who can reach the server sign up in the game. The eight-pilot limit always applies.

## 3. Bring your existing players across

On the current server, make a consistent backup:

```bash
cd "$HOME/star-trader-wip" && python3 save_server.py backup "$HOME/star-trader-move.sqlite3"
```

Copy that file to the new machine, then load it into the container:

```bash
docker compose stop server &&
docker compose cp star-trader-move.sqlite3 server:/data/progress.sqlite3 &&
docker compose start server
```

Logins (tokens), saves, feedback and news emails all move with it. Players keep their tokens; only the server address changes.

## Running admin commands

Run any `save_server.py` command inside the container. Files it writes land in `/data`; copy them out with `docker compose cp`:

```bash
docker compose exec server python save_server.py create-player Frank --token-file /data/frank.token
docker compose exec server python save_server.py invite --server https://203-0-113-7.sslip.io --token-file /data/frank.token --out /data/frank-invite.txt
docker compose cp server:/data/frank-invite.txt .
docker compose exec server python save_server.py feedback-list --status new
docker compose exec server python save_server.py backup /data/backup-$(date +%Y%m%d).sqlite3
```

## Updating

```bash
git pull --ff-only && docker compose up -d --build
```

Update the server before (or together with) a game release that changes the save format.
