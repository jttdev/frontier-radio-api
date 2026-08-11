#!/bin/sh
# Install or refresh the Germany mini-PC systemd recovery and health units.
# Build jttdev/frontier-radio-api:local before invoking this script as root.
set -eu

cd "$(dirname "$0")"

[ "$(id -u)" -eq 0 ] || {
    echo "run with sudo" >&2
    exit 1
}

command -v docker >/dev/null
command -v curl >/dev/null
docker image inspect jttdev/frontier-radio-api:local >/dev/null 2>&1 || {
    echo "image jttdev/frontier-radio-api:local is missing; build it before installing" >&2
    exit 1
}

install -d -m 0755 /var/lib/prometheus/node-exporter
install -m 0755 -o root -g root frontier-radio-api-health.sh \
    /usr/local/sbin/frontier-radio-api-health.sh
install -m 0644 -o root -g root \
    frontier-radio-api.service \
    frontier-radio-api-health.service \
    frontier-radio-api-health.timer \
    /etc/systemd/system/

systemctl daemon-reload
systemctl enable frontier-radio-api.service frontier-radio-api-health.timer
systemctl restart frontier-radio-api.service
systemctl start frontier-radio-api-health.service
systemctl restart frontier-radio-api-health.timer

systemctl is-active --quiet frontier-radio-api.service
systemctl is-active --quiet frontier-radio-api-health.timer
echo "Frontier Radio API recovery service and health timer are active"
