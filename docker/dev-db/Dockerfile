# The development and test database: the official PostgreSQL 16 Alpine image with
# pending Alpine updates applied and `gosu` removed, started as `postgres`.
#
# The official entrypoint uses `gosu` (also linked as `su-exec`) only to drop from root
# to `postgres`. It is a Go binary built with an old toolchain: on 2026-11-15 Docker Scout
# counted 4 critical and 30 high standard-library vulnerabilities in it. Started as
# `postgres`, the entrypoint never calls it, so nothing replaces it.
#
# The final stage is a flat copy on purpose: the scanner reads every layer, so a file
# deleted in a later layer still counts. A flat copy drops the base image's configuration,
# which is why ENV, VOLUME, EXPOSE, STOPSIGNAL, ENTRYPOINT and CMD are restated below with
# the official image's own values (`docker image inspect postgres:16-alpine`).
#
# Running as `postgres` (uid 70) the entrypoint cannot chown a data directory it does not
# own. A named volume works: an empty one takes the owner of the image's directory, and an
# existing one was written by the same uid.
FROM postgres:16-alpine AS official

RUN apk upgrade --no-cache \
 && rm -f /usr/local/bin/gosu /usr/local/bin/su-exec

FROM scratch
COPY --from=official / /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=en_US.utf8 \
    PG_MAJOR=16 \
    PGDATA=/var/lib/postgresql/data
VOLUME /var/lib/postgresql/data
EXPOSE 5432
STOPSIGNAL SIGINT
USER postgres
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
