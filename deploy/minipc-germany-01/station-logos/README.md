# Vendored station logos

Station artwork served at `http://10.3.0.12/station-logos/<file>.png` and
referenced from the `logo` field of the shared favorites list.

These are the original Frontier Silicon / Nuvola directory assets, taken from
`assets.wifiradiofrontier.com/assets/150x150/…`. They are drawn for the radios'
small displays, so they render better than a station's website favicon or a
scaled-down press logo.

| File | Station | Original CDN path |
| --- | --- | --- |
| `1live.png` | 1LIVE | `/assets/150x150/72/79/743482.png` |
| `asiafm-cantonese.png` | AsiaFM Cantonese | `/assets/150x150/13/23/935350.png` |
| `die-maus.png` | Die Maus | `/assets/150x150/81/32/635517.png` |
| `hr1.png` | hr1 | `/assets/150x150/37/52/196638.png` |
| `kcea-big-band.png` | KCEA 89.1 Big Band | `/assets/150x150/45/86/956155.png` |
| `radio-swiss-jazz.png` | Radio Swiss Jazz | `/assets/150x150/81/30/775522.png` |
| `radio-swiss-pop.png` | Radio Swiss Pop | `/assets/150x150/29/07/458975.png` |
| `solar-radio.png` | Solar Radio | `/assets/150x150/16/63/420280.png` |
| `somafm-seven-inch-soul.png` | SomaFM Seven Inch Soul | `/assets/150x150/74/18/302962.png` |
| `starpoint-radio.png` | Starpoint Radio | `/assets/150x150/29/59/100404.png` |
| `superfly-fm.png` | Superfly FM | `/assets/150x150/90/44/630117.png` |
| `wdr2-rheinland.png` | WDR 2 Rheinland | `/assets/150x150/35/03/767379.png` |
| `wefunk-radio.png` | WEFUNK Radio | `/assets/150x150/62/13/261769.png` |

Three stations are absent from the upstream catalogue and use the
broadcaster's own artwork instead, normalised to 150x150 to match the rest:

| File | Station | Source |
| --- | --- | --- |
| `goodlife.png` | GOODLIFE | `radiogoodlife.com/wp-content/uploads/2022/08/Logo_G_Radio_500px-370x370.png` |
| `the-face-radio.png` | The Face Radio | `liveradio.ie/files/images/571335/resized/180x172c/the_face_radio.jpg` |
| `wdr-cosmo.png` | WDR COSMO | `www1.wdr.de/radio/cosmo/ueber-uns/cosmo-logo-100~_v-square-m.jpg` |

Centre-crop non-square sources to a square before resizing. Padding them to
150x150 instead leaves visible bars on the radio display, which is obvious on
artwork with a dark background.

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
