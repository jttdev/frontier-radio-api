# Willich mini-PC deployment

This stack runs the self-hosted Frontier Silicon/Nuvola directory and
favorites backend for the Auna and Hama internet radios on the Germany LAN.

The Germany UDM resolves these exact directory endpoints to `10.3.0.12`:

- `auna.wifiradiofrontier.com` — older vendor-specific XML API
- `auna2.wifiradiofrontier.com` — older vendor-specific XML API fallback
- `hama.wifiradiofrontier.com` — Hama vendor-specific XML API
- `hama2.wifiradiofrontier.com` — Hama vendor-specific XML API fallback
- `pri.logon.wifiradiofrontier.com` — legacy FS2026 XML API used by NE-6146T11
- `airable.wifiradiofrontier.com` — newer shared JSON API

The UDM does not override `time.wifiradiofrontier.com` or
`update.wifiradiofrontier.com`, so NTP and firmware updates keep working.

## Deploy

The API is managed by `frontier-radio-api.service`, not by Docker's boot-time
container restoration alone. The service waits for the exact LAN bind address,
then force-recreates the container so a pre-DHCP port-bind failure cannot leave
it running without a network or published ports. It retries indefinitely and
requires the legacy XML endpoint to return a valid encrypted token.

Build the image before installing or restarting the unit; boot recovery uses
`--no-build` deliberately so a restart never performs a network-dependent image
build. The installer is idempotent.

```bash
ssh -o BatchMode=yes minipc-germany-01 '
  cd ~/frontier-radio-api &&
  mkdir -p deploy/minipc-germany-01/data deploy/minipc-germany-01/media &&
  git pull --ff-only &&
  docker compose -f deploy/minipc-germany-01/compose.yaml build radio-api &&
  sudo deploy/minipc-germany-01/install-service.sh
'
```

The ignored `data/` and `media/` directories contain station lists, podcast
state, the generated TLS certificate, and cached logos. The deployment uses
Radio-API's file-backed JSON cache because this is a small private instance.

The management UI is `http://10.3.0.12/gui/`. Open Internet Radio on a radio,
find its `GUI-Code` menu entry, and use that code to manage that radio's custom
stations and podcasts.

`frontier-radio-api-health.timer` probes the legacy XML endpoint every minute
and atomically writes
`/var/lib/prometheus/node-exporter/frontier-radio-api.prom`. The existing
`node_kubuntu_push` service sends `frontier_radio_api_up` to central
Prometheus. A failed endpoint still rewrites the file with value `0`; the file
mtime distinguishes a failed API from a stopped collector.

## Verify

```bash
dig @10.3.0.1 auna.wifiradiofrontier.com A +short
dig @10.3.0.1 auna2.wifiradiofrontier.com A +short
dig @10.3.0.1 hama.wifiradiofrontier.com A +short
dig @10.3.0.1 hama2.wifiradiofrontier.com A +short
dig @10.3.0.1 pri.logon.wifiradiofrontier.com A +short
dig @10.3.0.1 airable.wifiradiofrontier.com A +short
curl -fsS http://10.3.0.12/setupapp/iden/asp/BrowseXML/loginXML.asp?token=0
curl -kfsS -H 'Host: airable.wifiradiofrontier.com' https://10.3.0.12/
ssh -o BatchMode=yes minipc-germany-01 '
  systemctl is-active frontier-radio-api.service frontier-radio-api-health.timer
  docker ps --filter name=minipc-germany-01-radio-api-1
  cat /var/lib/prometheus/node-exporter/frontier-radio-api.prom
'
```

After changing the service or installer, verify the installed units before a
controlled reboot:

```bash
ssh -o BatchMode=yes minipc-germany-01 '
  sudo systemd-analyze verify \
    /etc/systemd/system/frontier-radio-api.service \
    /etc/systemd/system/frontier-radio-api-health.service \
    /etc/systemd/system/frontier-radio-api-health.timer
  upsc ups@localhost ups.status
'
```

After reboot, repeat the endpoint checks above, confirm `upsc` reports `OL`,
and confirm `wg show wg0 latest-handshakes` contains a current non-zero value.
