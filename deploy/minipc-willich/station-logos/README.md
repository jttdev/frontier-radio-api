# Vendored station logos

Station artwork served at `http://10.3.0.12/station-logos/<file>.png` and
referenced from the `logo` field of the shared favorites list.

These are the original Frontier Silicon / Nuvola directory assets, taken from
`assets.wifiradiofrontier.com/assets/150x150/…`. They are drawn for the radios'
small displays, so they render better than a station's website favicon or a
scaled-down press logo.

| File | Station | Original CDN path |
| --- | --- | --- |
| `die-maus.png` | Die Maus | `/assets/150x150/81/32/635517.png` |
| `wdr2-rheinland.png` | WDR 2 Rheinland | `/assets/150x150/35/03/767379.png` |

They must be vendored rather than linked: `assets.wifiradiofrontier.com` is a
CNAME to `airable.wifiradiofrontier.com`, which the Germany UDM overrides to
`10.3.0.12`. Every host on this LAN — including the Radio-API container that
would fetch and cache the logo — therefore resolves the asset CDN to this
server and gets a 303 instead of a PNG. A `logo` value pointing at the real CDN
silently falls back to the generic `media/default.png`.

To add another station's original logo, look its `<Logo>` element up on the
still-running upstream directory from a host that bypasses the local override,
then commit the file here:

```bash
IP=$(dig @1.1.1.1 +short assets.wifiradiofrontier.com | grep -E '^[0-9]' | head -1)
BASE=http://pri.logon.wifiradiofrontier.com
FAKE=0011223344556677889900112233   # synthetic; never send a real radio token

# 1. find the station id
curl -sS --resolve "pri.logon.wifiradiofrontier.com:80:$IP" \
  "$BASE/setupapp/fs/asp/BrowseXML/Search.asp?sSearchtype=2&Search=<name>&mac=$FAKE&dlang=eng&fver=4&startItems=1&endItems=10"

# 2. read its <Logo> from the station detail
curl -sS --resolve "pri.logon.wifiradiofrontier.com:80:$IP" \
  "$BASE/vtuner/station=<id>?mac=$FAKE&dlang=eng&fver=4"

# 3. download it, bypassing the local DNS override
curl -sS --resolve "assets.wifiradiofrontier.com:80:$IP" \
  -o <station>.png "http://assets.wifiradiofrontier.com/assets/150x150/<path>.png"
```

Use a synthetic `mac` for these lookups. The upstream directory answers without
authentication, and a real radio's token does not need to be disclosed to the
vendor to read public station metadata.
