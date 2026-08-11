#!/bin/sh
# Probe the local legacy XML directory path and expose one node_exporter
# textfile metric. The central Kubuntu pusher carries it to Prometheus.
set -eu

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
METRIC_FILE="${TEXTFILE_DIR}/frontier-radio-api.prom"
TMP_FILE=$(mktemp "${METRIC_FILE}.XXXXXX")
trap 'rm -f "$TMP_FILE"' EXIT HUP INT TERM

radio_api_up=0
if response=$(curl -fsS --max-time 5 \
    'http://10.3.0.12/setupapp/iden/asp/BrowseXML/loginXML.asp?token=0' \
    2>/dev/null); then
    if printf '%s\n' "$response" | grep -Eq \
        '^<EncryptedToken>[[:xdigit:]]+</EncryptedToken>$'; then
        radio_api_up=1
    fi
fi

if [ "$radio_api_up" -ne 1 ]; then
    echo "frontier-radio-api-health: legacy XML endpoint probe failed" >&2
fi

{
    echo '# HELP frontier_radio_api_up 1 if the local legacy XML directory endpoint returns a valid encrypted token'
    echo '# TYPE frontier_radio_api_up gauge'
    printf 'frontier_radio_api_up %s\n' "$radio_api_up"
} > "$TMP_FILE"

chmod 0644 "$TMP_FILE"
mv -f "$TMP_FILE" "$METRIC_FILE"
trap - EXIT HUP INT TERM
