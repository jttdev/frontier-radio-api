# YJ Janosch Home deployment

Second Radio-API instance for the internet radios at YJ Janosch Home, in CT 103
`utility-yj-janosch-home` (`10.18.0.13`) on `minipc-china-01`. It serves the
same favorites and radio registrations as the Germany instance, so a radio
moved from Germany finds its list unchanged.

## Shared state

`minipc-germany-01` is the master. Edit lists in the Germany GUI
(`http://10.3.0.12/gui/`); the China GUI (`http://10.18.0.13/gui/`) works, but
its edits are overwritten the next time Germany's state changes.

`frontier-radio-api-sync.timer` pulls `table.json`, `radios_*.json` and
`podcasts_*.json` every 5 minutes. The sites have no direct route, so the pull
runs over SSH through the Aliyun VPS (`lq@172.18.95.143`), which reaches both
sites over IPsec. Key `/root/.ssh/id_ed25519_radio-sync` in the CT is restricted
at both ends:

- Aliyun `lq` `authorized_keys`: `restrict,port-forwarding,permitopen="10.3.0.12:22"`.
- Germany `janosch` `authorized_keys`:
  `restrict,command="/usr/bin/rrsync -ro .../deploy/minipc-germany-01/data"`.

Host keys for both hops are pinned in `/var/lib/frontier-radio-api-sync/known_hosts`.

An apply happens only when Germany's copy changed since the last pull (kept in
`/var/lib/frontier-radio-api-sync/pulled/`). It writes the files as uid 82,
clears `data/cache` (the JSON cache holds `table.json` and the lists) and
restarts the container. A radio that first contacts this instance registers in
the local `table.json` and keeps working until Germany's state next changes;
for a permanent entry, register the radio against the Germany instance.

Station logo URLs in the lists point at `http://10.3.0.12/station-logos/`; the
apply rewrites them to `10.18.0.13`, which serves the same vendored files from
`../minipc-germany-01/station-logos/`. A newly vendored logo therefore needs a
`git pull` in CT 103 as well.

Not synced, per instance: `env.json`, the generated TLS pair, `cache/`, logs,
and `media/`.

The `CONF_MEDIAYOU_DEVICES` map in `compose.yaml` matches Germany's, so an
IR-130 keeps its profile on either site. The Skytune unit holds device-local
presets pushed by `../minipc-germany-01/sync-skytune-presets.sh`; once it is
here, push them from CT 103 against this instance after a list change:

```bash
RADIO_API_BASE=http://10.18.0.13 \
RADIO_API_DATA=/opt/frontier-radio-api/deploy/yj-janosch-home/data/radios_2.json \
deploy/minipc-germany-01/sync-skytune-presets.sh <radio-ip> 28A1EBFD12B8
```

## Moving a radio from Germany

Nothing to change on the radio or in either Radio-API: its registration and
profile are already in the synced `table.json`. Join it to `tdmt_main`, and
after it first appears give it a fixed lease in
`infra-configs/unifi/sites/yj-janosch-home/main.tf` `clients` (note the radio
ID, as in the Germany table in the repo `CLAUDE.md`). A Skytune unit then needs
the preset push above.

## Network

The radios join the `tdmt_main` SSID (Default VLAN). That VLAN's DNS is the
Mihomo gw (`10.18.0.2`), whose `hosts:` block in
`infra-configs/proxy-rules/mihomo/yj-janosch-home.yaml` resolves the directory
endpoints to `10.18.0.13`: the same seven names the Germany UDM overrides (see
`../minipc-germany-01/README.md`). Time and firmware-update hosts stay public.
Station streams leave through the gw's full proxy.

## Deploy

```bash
ssh -o BatchMode=yes minipc-china-01 'pct exec 103 -- sh -c "
  cd /opt/frontier-radio-api && git pull --ff-only &&
  mkdir -p deploy/yj-janosch-home/data deploy/yj-janosch-home/media &&
  docker compose -f deploy/yj-janosch-home/compose.yaml build radio-api &&
  deploy/yj-janosch-home/install-service.sh"'
```

## Verify

```bash
ssh -o BatchMode=yes minipc-china-01 'pct exec 103 -- sh -c "
  systemctl is-active frontier-radio-api.service frontier-radio-api-health.timer frontier-radio-api-sync.timer
  curl -fsS http://10.18.0.13/setupapp/iden/asp/BrowseXML/loginXML.asp?token=0
  systemctl start frontier-radio-api-sync.service && journalctl -t frontier-radio-api-sync -n 3 --no-pager
  cat /var/lib/prometheus/node-exporter/frontier-radio-api*.prom"'
dig @10.18.0.2 auna.wifiradiofrontier.com A +short   # 10.18.0.13
```

`frontier_radio_api_up` and `frontier_radio_api_sync_*` reach Prometheus with
the CT's `node_kubuntu_push` instance `utility-yj-janosch-home`.
