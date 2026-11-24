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

Configure the server provider's firewall as well, if it has one. The HTTPS
setup below requires public ports 80 and 443; the application proxy itself
will only be reachable from the server.

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
  Keep `localhost` in this list for the Docker health checks.
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

Continue with the HTTPS setup below before using the site. Replace
`your-domain` with a name listed in `ALLOWED_HOSTS`.

## 5. Configure HTTPS before public use

This guide uses [Caddy](https://caddyserver.com/) on the Linux host as the
public HTTPS reverse proxy. Caddy obtains and renews a trusted certificate
automatically. The Docker Nginx proxy remains in place for the app, static
files, and media, but is bound to localhost so it cannot be accessed directly
from the internet.

### 5.1 Point your domain to the server

At your domain's DNS provider, create:

- An `A` record for the root domain (often shown as `@`) pointing to the
  server's public IPv4 address.
- Optionally, a `CNAME` record for `www` pointing to the root domain, or an
  `A` record for `www` pointing to the same IP.

If you publish an `AAAA` record, it must point to a working IPv6 address on
this server. Otherwise, remove it; an incorrect IPv6 record can prevent
certificate issuance or make the site unreachable for some visitors. Wait for
DNS changes to propagate before continuing.

Allow inbound TCP ports 80 and 443 in both the server firewall and any
provider firewall. For UFW:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

### 5.2 Keep the application proxy private

The Compose configuration binds Nginx to `127.0.0.1:8080` on the host. Apply
this port change to an already-running deployment:

```bash
sudo docker compose up -d
```

Do not expose port 8080 through the server or provider firewall. Only Caddy
should accept public web traffic.

### 5.3 Install and configure Caddy

Install Caddy on the host using its official
[Ubuntu/Debian package instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian).
This guide assumes the package runs Caddy as a systemd service.

Edit `/etc/caddy/Caddyfile` and replace the example names with the domain(s)
you want to serve:

```caddyfile
example.org, www.example.org {
    reverse_proxy 127.0.0.1:8080
}
```

Validate the file and reload Caddy:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

Caddy will request certificates after DNS resolves to this server and ports 80
and 443 are reachable. It also redirects HTTP visitors to HTTPS. If
certificate issuance fails, inspect
`sudo journalctl -u caddy --since "10 minutes ago"` and recheck DNS and
firewall settings.

### 5.4 Enable Django's HTTPS protections

After Caddy has obtained a certificate, edit `.env` and list the exact hosts
and HTTPS origins users will use. For example:

```ini
ALLOWED_HOSTS=example.org,www.example.org,localhost
CSRF_TRUSTED_ORIGINS=https://example.org,https://www.example.org
ENABLE_HTTPS_HARDENING=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=0
```

Save the file with restricted permissions (`chmod 600 .env`) and recreate the
web container to apply the settings:

```bash
sudo docker compose up -d --force-recreate web
```

The HTTPS hardening setting makes Django trust the scheme forwarded through
Caddy and Nginx, redirect HTTP requests to HTTPS, and mark session/CSRF cookies
secure. Keep `SECURE_HSTS_SECONDS=0` until you have confirmed HTTPS works for
every subdomain; then set it to `31536000` and recreate the web container.

Verify the redirect and HTTPS response:

```bash
curl -I http://example.org/
curl -I https://example.org/login/
sudo docker compose logs --tail=100 nginx web
```

The HTTP request should redirect to HTTPS, and the HTTPS request should return
a successful page response. Open the HTTPS site in a browser and confirm you
can sign in before considering the setup complete.

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
