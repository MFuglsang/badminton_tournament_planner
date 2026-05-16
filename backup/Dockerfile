FROM postgres:16-alpine

# pg_dump is included in postgres image; add tar/gzip/bash and (optional) aws-cli
RUN apk add --no-cache \
        bash \
        coreutils \
        tzdata \
        gzip \
        tar \
        findutils \
        aws-cli

ENV TZ=Europe/Copenhagen
ENV BACKUP_HOUR=2
ENV BACKUP_RETENTION_DAILY=14
ENV BACKUP_RETENTION_MONTHLY=12
ENV BACKUP_ON_START=0

COPY backup.sh   /usr/local/bin/backup.sh
COPY restore.sh  /usr/local/bin/restore.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh \
             /usr/local/bin/restore.sh \
             /usr/local/bin/entrypoint.sh

VOLUME ["/backups"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
