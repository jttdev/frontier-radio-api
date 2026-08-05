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

```bash
ssh -o BatchMode=yes willich '
  cd ~/frontier-radio-api/deploy/minipc-willich &&
  mkdir -p data media &&
  git pull --ff-only &&
  docker compose up -d --build
'
```

The ignored `data/` and `media/` directories contain station lists, podcast
state, the generated TLS certificate, and cached logos. The deployment uses
Radio-API's file-backed JSON cache because this is a small private instance.

The management UI is `http://10.3.0.12/gui/`. Open Internet Radio on a radio,
find its `GUI-Code` menu entry, and use that code to manage that radio's custom
stations and podcasts.

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
ssh -o BatchMode=yes willich '
  cd ~/frontier-radio-api/deploy/minipc-willich &&
  docker compose ps && docker compose logs --tail=50
'
```
