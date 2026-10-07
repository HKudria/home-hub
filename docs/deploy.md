# Deploying Home Hub (Proxmox LXC + Docker)

This guide deploys Home Hub on a Proxmox LXC container running the FastAPI web
UI and the Telegram bot in a single Docker container. All persistent data
(SQLite database, photos, backups) lives in the `./data` directory on the host
and survives container rebuilds.

## 1. Create the LXC and install Docker

In the Proxmox web UI, create a new LXC container:

- **Template:** Debian 12 (bookworm)
- **RAM:** 1 GB
- **Disk:** 8 GB is plenty (the database and photos are small)
- **Network:** a static DHCP reservation is convenient — the web UI and the
  bot will live at one address

Start the container, open its console, and install Docker:

```bash
apt update && apt -y install curl git
curl -fsSL https://get.docker.com | sh
```

## 2. Get the code and configure `.env`

```bash
cd /opt
git clone <your-repo-url> home-hub
cd home-hub
cp .env.example .env
nano .env
```

Fill in the values:

- **`TELEGRAM_BOT_TOKEN`** — in Telegram, talk to
  [@BotFather](https://t.me/BotFather): send `/newbot`, pick a display name and
  a username ending in `bot`, then copy the token it gives you
  (`123456789:AAF...`) into this variable.
- **`ADMIN_TELEGRAM_ID`** — your numeric Telegram user ID. Message
  [@userinfobot](https://t.me/userinfobot) and it replies with your ID. The
  admin is automatically allowed to use the bot and approves other users.
- **`ZAI_API_KEY`** — your z.ai API key, used to extract medicine data from
  photos and interpret text messages.
- **`WEB_PASSWORD`** — password for the web UI login page.
- **`DATA_DIR=/data`** — **important:** the `.env.example` default
  (`./data`) works for running without Docker, but inside the container it
  must be `/data`, which is the path mounted from the host's `./data`
  directory by docker-compose. If you leave it as `./data`, the database ends
  up inside the container and is lost on rebuild.
- Optional: `DAILY_CHECK_HOUR` (hour of the daily stock check, default `9`),
  `BACKUP_KEEP_DAYS` (default `14`), model names, `ZAI_BASE_URL`.

## 3. Start

```bash
docker compose up -d --build
```

Check that it is running:

```bash
docker compose ps
docker compose logs -f    # Ctrl+C to stop following
```

On startup the app creates `data/hub.db`, runs migrations, and — if
`TELEGRAM_BOT_TOKEN` is set — starts bot polling and the scheduler (daily
check, hourly AI retry, nightly 03:00 backup). Without a token it starts in
web-only mode.

## 4. Open the web UI over VPN and add it to the home screen

Open `http://<lxc-ip>:8000` from your phone (e.g. `http://192.168.1.50:8000`).
Home Hub has no public HTTPS — it is meant to be reached from inside your home
network, typically over your VPN when away from home. Log in with
`WEB_PASSWORD`.

To get an app-like icon: in the phone's browser menu choose **Add to Home
Screen**. The page is responsive and sets a proper name/icon for the shortcut.

## 5. Approve bot users

In Telegram, find your bot by the username you gave BotFather and send
`/start`:

- As the admin you are already allowed — the bot confirms immediately.
- Other family members who send `/start` get a "waiting for approval" reply,
  and the admin receives a message with **Approve** / **Decline** buttons.
  Approve them once; they stay allowed.
- Optionally, each user can pick their language with `/lang pl` (also
  `ru`, `uk`, `en`).

## 6. Restore from backup

Backups are **gzipped raw SQLite databases**, not SQL dumps. Every night at
03:00 the app writes `data/backups/hub-YYYY-MM-DD.db.gz` (a consistent
snapshot of the database, compressed) and keeps the last `BACKUP_KEEP_DAYS`
days. Because the backup is a compressed copy of the database file itself,
restoring means gunzipping it back into place.

On the LXC host, from the repo directory:

```bash
# 1. Stop the container so nothing writes to the database
docker compose stop

# 2. Replace the live database with the chosen backup
gunzip -c data/backups/hub-2026-10-07.db.gz > data/hub.db

# 3. Start the container again
docker compose start
```

The gunzipped file is a directly usable SQLite database — no import step is
needed. Photos are not part of backups; keep a normal file backup of
`data/photos/` if the pictures matter to you.

## 7. Updating

```bash
git pull
docker compose up -d --build
```

This rebuilds the image with the new code and restarts the container. All data
in `./data` (database, photos, backups) is untouched by rebuilds.
