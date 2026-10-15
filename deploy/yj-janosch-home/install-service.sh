#!/bin/sh
# Install or refresh the YJ Janosch Home recovery, health and sync units.
# Build jttdev/frontier-radio-api:local before invoking this script as root.
set -eu

cd "$(dirname "$0")"

[ "$(id -u)" -eq 0 ] || {
    echo "run as root" >&2
    exit 1
}

command -v docker >/dev/null
command -v curl >/dev/null
command -v rsync >/dev/null
docker image inspect jttdev/frontier-radio-api:local >/dev/null 2>&1 || {
    echo "image jttdev/frontier-radio-api:local is missing; build it before installing" >&2
    exit 1
}

install -d -m 0755 /var/lib/prometheus/node-exporter
install -m 0755 -o root -g root frontier-radio-api-health.sh \
    /usr/local/sbin/frontier-radio-api-health.sh
install -m 0755 -o root -g root frontier-radio-api-sync.sh \
    /usr/local/sbin/frontier-radio-api-sync.sh
install -m 0644 -o root -g root \
    frontier-radio-api.service \
    frontier-radio-api-health.service \
    frontier-radio-api-health.timer \
    frontier-radio-api-sync.service \
    frontier-radio-api-sync.timer \
    /etc/systemd/system/

systemctl daemon-reload
systemctl enable frontier-radio-api.service frontier-radio-api-health.timer \
    frontier-radio-api-sync.timer
systemctl restart frontier-radio-api.service
systemctl start frontier-radio-api-health.service
systemctl restart frontier-radio-api-health.timer frontier-radio-api-sync.timer

systemctl is-active --quiet frontier-radio-api.service
systemctl is-active --quiet frontier-radio-api-health.timer
systemctl is-active --quiet frontier-radio-api-sync.timer
echo "Frontier Radio API recovery service, health and sync timers are active"
