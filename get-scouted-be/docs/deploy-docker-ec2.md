# Deploying GetScouted Backend to AWS EC2 with Docker

This guide deploys the full GetScouted stack on a single EC2 server using Docker.
Everything (Django + Postgres, fronted by Nginx) runs as Docker containers.

No prior Docker or cloud experience required — every command is explained.

---

## What You Will End Up With

```
Internet
   │
   ▼
Nginx container (ports 80 / 443)
   │
   └──▶ Gunicorn container (port 8000)   ← Django REST API
         │
         └── PostgreSQL container
```

All containers are defined in `docker-compose.prod.yml` and managed together.
The player/club/transfer dataset is baked into the Docker image at build time
(`dataset/` in this repo, copied to `/app/dataset` — see the `Dockerfile`), so
there's nothing extra to fetch on the server.

---

## Prerequisites

- An **AWS account**
- Your code pushed to the **GS-Python-Backend** GitHub repo (private is fine)
- A **domain name** pointing to your server (needed for HTTPS in Part 7 — optional
  for a first pass over plain HTTP)
- Your `ANTHROPIC_API_KEY` if you want AI-powered search/reports live (optional —
  the app degrades gracefully to a keyword fallback without one)

---

## Part 1 — Launch an EC2 Instance

### Step 1.1 — Log in to AWS Console

Go to [console.aws.amazon.com](https://console.aws.amazon.com) → search for **EC2** → click it.

### Step 1.2 — Launch a new instance

Click the orange **"Launch instance"** button and fill in:

| Field | Value |
|-------|-------|
| Name | `get-scouted-be` |
| AMI | **Ubuntu Server 24.04 LTS** (64-bit **x86**) |
| Instance type | `t3.small` (2 CPU, 2 GB RAM) — fine to start; see note below |
| Key pair | Create/reuse a key pair → download the `.pem` file |
| Storage | 30 GB, gp3 |

> **Instance sizing note:** this stack has no Celery/Redis/GPU needs — it's a
> plain Django REST API plus Postgres, both on the same box. The one thing to
> watch is memory: each gunicorn worker independently loads pandas/scikit-learn
> and caches scoring data in-process, and Postgres is also running locally. The
> compose file below defaults to **2 gunicorn workers**, which fits comfortably
> in `t3.small`'s 2 GB. If you see OOM kills in `docker compose -f
> docker-compose.prod.yml logs web`, bump the instance to `t3.medium` (4 GB)
> rather than adding more workers.
>
> Picked `t2.small` instead? It works, but `t3`/`t4g` are newer-generation and
> generally cheaper for the same specs — no reason to prefer `t2` here.

### Step 1.3 — Firewall (Security Group)

Under **"Network settings"** → click **"Edit"** → set these rules:

| Type | Port | Source | Why |
|------|------|--------|-----|
| SSH | 22 | My IP | So only you can connect |
| HTTP | 80 | Anywhere | Public web traffic |
| HTTPS | 443 | Anywhere | Secure web traffic |

> **Do NOT open port 8000.** That's internal — Nginx handles all public traffic.

### Step 1.4 — Launch and get the IP

Click **"Launch instance"**. After ~60 seconds, go to **EC2 → Instances**, click your instance,
and copy the **Public IPv4 address**.

---

## Part 2 — Connect to the Server

```bash
# Mac/Linux — make the key file private (SSH refuses loose permissions)
chmod 400 ~/Downloads/your-key.pem

# Connect (replace YOUR_IP with the IP from Step 1.4)
ssh -i ~/Downloads/your-key.pem ubuntu@YOUR_IP
```

You should see the Ubuntu welcome screen and a prompt ending in `ubuntu@...:~$`.

---

## Part 3 — Install Docker

Ubuntu's default package repo does not include `docker-compose-plugin`.
You must add Docker's official repository first:

```bash
# Install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker's official apt repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start Docker and set it to start on reboot
sudo systemctl enable docker
sudo systemctl start docker

# Allow your user to run Docker without sudo
sudo usermod -aG docker ubuntu
newgrp docker
```

Verify:

```bash
docker --version          # Docker version 24.x.x or later
docker compose version    # Docker Compose version v2.x.x
```

---

## Part 4 — Get Your Code on the Server

```bash
cd /home/ubuntu
git clone git@github.com:GetScouted2010/GS-Python-Backend---4-8-26.git app
cd app
```

(Use an HTTPS clone URL instead if you haven't set up a deploy key on this server.)

---

## Part 5 — Configure Environment Variables

### Step 5.1 — Create the production .env file

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

Fill in every value:

```dotenv
SECRET_KEY=replace-with-a-very-long-random-string
ALLOWED_HOSTS=api.yourdomain.com

DATABASE_URL=postgresql://getscouted:YOUR_STRONG_DB_PASSWORD@db:5432/getscouted
DB_PASSWORD=YOUR_STRONG_DB_PASSWORD

DATASET_DIR=/app/dataset

HTTPS_ENABLED=False

LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

> **Important:** the hostname `db` in `DATABASE_URL` is a Docker service name, not
> `localhost`. Docker's internal network routes it to the right container automatically.

Generate a strong `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Save and exit: `Ctrl+X` → `Y` → `Enter`.

---

## Part 6 — Build the Docker Image

```bash
docker build -t get-scouted-be:latest .
```

Takes a couple of minutes the first time (installing Django, DRF, pandas, scikit-learn, etc.).

---

## Part 7 — Get an SSL Certificate (HTTPS) — optional but recommended

Your domain must point to this server's IP before this step. In your domain registrar
create an **A record**: Host `api` (or `@`), Value = your EC2 Public IPv4 address.

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d api.yourdomain.com
```

Certificate files land in `/etc/letsencrypt/live/api.yourdomain.com/`. Update
`nginx/getscouted.conf` to add a `listen 443 ssl;` server block pointing at those
paths (mirror the pattern from any other project's Nginx TLS block), then set
`HTTPS_ENABLED=True` in `.env.prod`.

---

## Part 8 — Run Migrations and Load the Dataset

```bash
# Start just the database
docker compose -f docker-compose.prod.yml up -d db

# Wait a few seconds for it to be healthy
sleep 10

# Apply schema migrations
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --no-input

# Load the player/club/transfer dataset into Postgres (idempotent — safe to re-run).
# The compatibility-scores step is the slowest (~3-4 min, ~8.1M rows).
docker compose -f docker-compose.prod.yml run --rm web python manage.py import_all

# Collect static files (Nginx will serve these — Django admin, DRF browsable API, etc.)
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --no-input

# Create an admin superuser
docker compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser
```

---

## Part 9 — Start All Services

```bash
docker compose -f docker-compose.prod.yml up -d
```

This starts all 3 containers (db, web, nginx) in the background.

```bash
docker compose -f docker-compose.prod.yml ps
```

You should see all services **Up**/**running**. Your API is now live at
`http://YOUR_IP/api/docs/` (or `https://api.yourdomain.com/api/docs/` after Part 7).

---

## Part 10 — Auto-Renew SSL Certificates

If you set up HTTPS in Part 7, certificates expire after 90 days:

```bash
sudo certbot renew --dry-run
sudo crontab -e
```

Add:

```
0 3 * * * certbot renew --quiet && docker compose -f /home/ubuntu/app/docker-compose.prod.yml exec nginx nginx -s reload
```

---

## Part 11 — Deploying Code Updates

Every time you push new code:

```bash
cd /home/ubuntu/app
make docker-deploy
```

This is a shortcut for: `git pull` → rebuild the image → run any new migrations →
`collectstatic` → recreate the `web` container (db/nginx are left running).
It does **not** re-run `import_all` — run that manually if the dataset itself changed.

---

## Local Development with Docker

To run the full stack on your laptop (no cloud needed):

```bash
cp .env.docker.example .env.docker
make docker-up          # or: docker compose up -d

# First time only:
docker compose exec web python manage.py migrate
docker compose exec web python manage.py import_all
docker compose exec web python manage.py createsuperuser
```

API is available at `http://localhost:8000/api/docs/`.

```bash
make docker-down                 # stop everything
docker compose down -v           # stop AND delete the database volume (full reset)
```

---

## Useful Commands

All wired up as `make` targets (`make help` lists everything) — the prod ones
operate on `docker-compose.prod.yml`:

```bash
make docker-logs            # follow logs for all prod containers
make docker-logs-web        # just the web/gunicorn container
make docker-logs-db         # just Postgres
make docker-shell           # Django shell inside the running web container
make docker-migrate         # run migrations
make docker-superuser       # create an admin user
docker stats                # container resource usage — check for memory pressure
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `django.core.exceptions.ImproperlyConfigured` | Missing variable in `.env.prod` — check every line against `.env.prod.example` |
| `could not connect to server` (Postgres) | `db` container not healthy yet — wait 15s and retry |
| `502 Bad Gateway` from Nginx | `web` container is down — check `docker compose -f docker-compose.prod.yml ps` and `make docker-logs-web` |
| `504 Gateway Timeout` on a matching/search endpoint | Expected for the uncached arbitrary-club matching endpoints (can take up to ~2 min) — already accounted for via `proxy_read_timeout 180s` / gunicorn `--timeout 180`. If it still happens, the request is genuinely stuck — check `make docker-logs-web`. |
| Container killed / restarting in a loop | Likely OOM on `t3.small` — check `docker stats` / `dmesg \| grep -i oom`, then upgrade to `t3.medium` |
| `certificate not found` | SSL cert path wrong in `nginx/getscouted.conf` — double-check the domain name |

### Reset everything and start fresh

```bash
docker compose -f docker-compose.prod.yml down -v   # stops containers + deletes volumes
docker compose -f docker-compose.prod.yml up -d      # starts fresh
```

> **Warning:** `-v` deletes your database — you'll need to re-run `migrate` and `import_all`.

---

## Security Checklist

Before going live, verify:

- [ ] `SECRET_KEY` is a long random string (not the example placeholder)
- [ ] Port 22 is restricted to your IP in the AWS Security Group
- [ ] Port 8000 is NOT open in the AWS Security Group
- [ ] `.env.prod` is in `.gitignore` (never committed to git)
- [ ] `DB_PASSWORD` is a strong unique password
- [ ] HTTPS is working (`https://` in the browser shows a padlock) before handling real user data
- [ ] `ANTHROPIC_API_KEY` is a real production key, not left blank in a prod deploy that expects AI search
