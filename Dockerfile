FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# gettext is required by Django's makemessages / compilemessages commands
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated non-root user/group to run the application
RUN groupadd --system --gid 1001 app \
    && useradd  --system --uid 1001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files – does not touch the database and is safe to run during build
RUN SECRET_KEY=build-dummy python manage.py collectstatic --noinput

# Make entrypoint executable and hand ownership of /app to the non-root user.
# Also strip CRLF line endings in case the repo was checked out on Windows
# with autocrlf=true (otherwise Linux can't exec the shebang).
RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
