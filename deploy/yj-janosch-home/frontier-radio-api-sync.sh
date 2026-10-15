#!/bin/sh
# Keep the YJ Janosch Home Radio-API on the same favorites and radio
# registrations as minipc-germany-01, which is the master: lists are edited
# in the Germany GUI (http://10.3.0.12/gui/).
#
# The two sites have no direct route; the pull rides an SSH jump through the
# Aliyun VPS, which reaches both over IPsec. Both ends restrict this key:
# Aliyun lq allows only a forward to 10.3.0.12:22, Germany janosch runs only
# `rrsync -ro` on the Radio-API data directory.
#
# Germany's state is applied only when it changed since the last pull, not
# whenever the local files differ: a radio first seen here writes itself into
# the local table.json and would otherwise be reverted and re-registered on
# every run. Such a local entry lasts until Germany's state next changes.
#
# The app caches table.json and the lists in data/cache (JSON cache backend),
# so an apply clears that cache and restarts the container.
set -eu
# $FILTER carries rsync patterns word-split on purpose; never glob them.
set -f

DEPLOY=/opt/frontier-radio-api/deploy/yj-janosch-home
DATA="$DEPLOY/data"
STATE=/var/lib/frontier-radio-api-sync
KEY=/root/.ssh/id_ed25519_radio-sync
JUMP=lq@172.18.95.143
SRC=janosch@10.3.0.12
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
METRIC_FILE="$TEXTFILE_DIR/frontier-radio-api-sync.prom"

SSH="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20 -o UserKnownHostsFile=$STATE/known_hosts -o StrictHostKeyChecking=yes"
FILTER="--include=table.json --include=radios_*.json --include=podcasts_*.json --exclude=*"

now=$(date +%s)
last_change=$(sed -n 's/^frontier_radio_api_sync_last_change_timestamp_seconds //p' "$METRIC_FILE" 2>/dev/null || true)
last_success=$(sed -n 's/^frontier_radio_api_sync_last_success_timestamp_seconds //p' "$METRIC_FILE" 2>/dev/null || true)
ok=0

write_metrics() {
    tmp=$(mktemp "$METRIC_FILE.XXXXXX")
    {
        echo '# HELP frontier_radio_api_sync_ok 1 if the last pull from minipc-germany-01 succeeded'
        echo '# TYPE frontier_radio_api_sync_ok gauge'
        echo "frontier_radio_api_sync_ok $ok"
        echo '# HELP frontier_radio_api_sync_last_run_timestamp_seconds Last sync run'
        echo '# TYPE frontier_radio_api_sync_last_run_timestamp_seconds gauge'
        echo "frontier_radio_api_sync_last_run_timestamp_seconds $now"
        if [ -n "$last_success" ]; then
            echo '# HELP frontier_radio_api_sync_last_success_timestamp_seconds Last successful pull'
            echo '# TYPE frontier_radio_api_sync_last_success_timestamp_seconds gauge'
            echo "frontier_radio_api_sync_last_success_timestamp_seconds $last_success"
        fi
        if [ -n "$last_change" ]; then
            echo '# HELP frontier_radio_api_sync_last_change_timestamp_seconds Last time Germany state was applied'
            echo '# TYPE frontier_radio_api_sync_last_change_timestamp_seconds gauge'
            echo "frontier_radio_api_sync_last_change_timestamp_seconds $last_change"
        fi
    } > "$tmp"
    chmod 0644 "$tmp"
    mv -f "$tmp" "$METRIC_FILE"
}
trap write_metrics EXIT

mkdir -p "$STATE/pulled" "$STATE/incoming"

# shellcheck disable=SC2086
rsync -rt --delete $FILTER \
    -e "$SSH -o ProxyCommand='$SSH -W %h:%p $JUMP'" \
    "$SRC:./" "$STATE/incoming/"

[ -s "$STATE/incoming/table.json" ] || {
    echo "frontier-radio-api-sync: pulled state has no table.json" >&2
    exit 1
}

# shellcheck disable=SC2086
changes=$(rsync -rc --delete --dry-run --itemize-changes $FILTER \
    "$STATE/incoming/" "$STATE/pulled/")

if [ -n "$changes" ] || [ ! -s "$DATA/table.json" ]; then
    # shellcheck disable=SC2086
    rsync -rc --delete --chown=82:82 --chmod=F644 $FILTER \
        "$STATE/incoming/" "$DATA/"
    # shellcheck disable=SC2086
    rsync -rc --delete $FILTER "$STATE/incoming/" "$STATE/pulled/"
    find "$DATA/cache" -mindepth 1 -delete 2>/dev/null || true
    docker compose -f "$DEPLOY/compose.yaml" restart radio-api >/dev/null
    logger -t frontier-radio-api-sync "applied Germany state: $(printf '%s' "$changes" | tr '\n' ' ')"
    last_change=$now
fi

last_success=$now
ok=1
