FROM postgres:16-alpine

# pg_dump is included in postgres image; add tar/gzip/bash, age (encryption),
# and (optional) aws-cli for off-site sync.
RUN apk add --no-cache \
        bash \
        coreutils \
        tzdata \
        gzip \
        tar \
        findutils \
        age \
        aws-cli

ENV TZ=Europe/Copenhagen
ENV BACKUP_HOUR=2
ENV BACKUP_RETENTION_DAILY=14
ENV BACKUP_RETENTION_MONTHLY=12
ENV BACKUP_ON_START=0

COPY backup.sh   /usr/local/bin/backup.sh
COPY restore.sh  /usr/local/bin/restore.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
# Strip any CRLF line endings (in case the repo was checked out on Windows
# with autocrlf=true) — Linux kernel refuses to exec a script whose shebang
# line ends in \r and produces "no such file or directory".
RUN sed -i 's/\r$//' /usr/local/bin/backup.sh \
                     /usr/local/bin/restore.sh \
                     /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/backup.sh \
                /usr/local/bin/restore.sh \
                /usr/local/bin/entrypoint.sh

VOLUME ["/backups"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
