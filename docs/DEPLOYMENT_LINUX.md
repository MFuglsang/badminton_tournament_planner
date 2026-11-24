# Deploy on a Linux server

This guide deploys the application on a new Ubuntu LTS or Debian stable server
using the repository's Docker Compose stack. It assumes you have a sudo user
and a domain name pointing to the server. Docker runs the Django application,
PostgreSQL, and Nginx; Python does not need to be installed on the host.

## 1. Prepare the server

Connect over SSH and update the system:

```bash
sudo apt update
sudo apt upgrade -y
```

If you use UFW, allow SSH before enabling the firewall so you do not lock
yourself out, then allow HTTP:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw enable
sudo ufw status
```

Configure the server provider's firewall as well, if it has one. The Compose
configuration currently exposes HTTP on port 80 only.

## 2. Install Docker Engine and Compose

Install Docker Engine and the Compose plugin from Docker's official
[Ubuntu](https://docs.docker.com/engine/install/ubuntu/) or
[Debian](https://docs.docker.com/engine/install/debian/) repository. The
following commands set up the repository for either supported distribution:

```bash
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
. /etc/os-release
sudo curl -fsSL "https://download.docker.com/linux/${ID}/gpg" \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
```

Check that Docker and Compose are installed:

```bash
sudo docker --version
sudo docker compose version
```

This guide uses `sudo docker` rather than adding the login user to the
`docker` group, which grants root-equivalent access.

## 3. Download the application and set its secrets

```bash
git clone https://github.com/MFuglsang/badminton_tournament_planner.git
cd badminton_tournament_planner
cp .env.example .env
chmod 600 .env
```

Generate secret values:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Edit `.env` with `nano .env` (or another editor). Replace the example values:

- `SECRET_KEY`: use the first generated value.
- `POSTGRES_PASSWORD`: use the second generated value.
- `ALLOWED_HOSTS`: set the domain names used to access the site, separated
  by commas, for example `tournaments.example.org,www.tournaments.example.org`.
- `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, and
  `DJANGO_SUPERUSER_PASSWORD`: set the initial administrator account and a
  unique, strong password.

Do not commit or share `.env`. Keep its permissions restricted. Leave
`ENABLE_HTTPS_HARDENING=False` until HTTPS is actually configured; enabling it
without TLS will break access to the site.

## 4. Start the services

From the cloned repository directory, build and start the application:

```bash
sudo docker compose up -d --build
sudo docker compose ps
```

On startup, the web container collects static files, applies database
migrations, and creates the configured administrator if it does not already
exist. Check startup output if a service is not healthy:

```bash
sudo docker compose logs --tail=100 web
sudo docker compose logs --tail=100 nginx
```

After confirming the administrator account was created, remove
`DJANGO_SUPERUSER_PASSWORD` from `.env` and recreate the web container so the
password is no longer kept in the environment:

```bash
sudo docker compose up -d --force-recreate web
```

Visit `http://your-domain/` and sign in. Replace `your-domain` with a name
listed in `ALLOWED_HOSTS`.

## 5. Configure HTTPS before public use

**The included Nginx configuration serves HTTP only. Do not use the login or
send passwords over a public HTTP connection.** Before public use, configure
TLS termination with a trusted certificate using an HTTPS reverse proxy or
hosting service. Merely changing Django's HTTPS settings does not install or
configure TLS.

The TLS setup must ensure Django receives the original host and
`X-Forwarded-Proto: https`. The bundled Nginx currently sets that header from
its own connection, so an outer TLS proxy forwarding plain HTTP to it needs
additional proxy configuration; forwarding to the bundled Nginx alone is not
enough. After verifying that Django recognizes requests as HTTPS, set these
values in `.env`:

```ini
CSRF_TRUSTED_ORIGINS=https://your-domain
ENABLE_HTTPS_HARDENING=True
```

Include every HTTPS site origin users will access in `CSRF_TRUSTED_ORIGINS`,
comma-separated. Recreate the web container to apply environment changes:

```bash
sudo docker compose up -d --force-recreate web
```

## Updates and data

To update the application, fetch the latest repository changes and rebuild:

```bash
git pull
sudo docker compose up -d --build
```

Database migrations run automatically when the web container starts. Database
and uploaded media are kept in Docker volumes. The Compose backup service
writes scheduled database and media archives under `./backups/` by default;
configure the backup options in `.env` and keep an off-server copy of backups
for disaster recovery. See [How to Run](HOW_TO_RUN.md#backups--restore) for
backup and restore commands.

To inspect running services or stop them:

```bash
sudo docker compose ps
sudo docker compose down
```

`docker compose down` preserves the named data volumes. Do not use
`docker compose down --volumes` unless you intend to delete the database,
uploaded media, and collected static files.
