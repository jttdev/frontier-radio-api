# CS-806 shared favorites

HanRongDa/generic CS-806 radios (observed app `0.43.3.ru`, MCU `C920 V05.2`)
use `5788230443.airable.io`, HTTP Basic-shaped per-request signatures, and the
`cachip 1.0` user agent. They accept this deployment's self-signed TLS certificate.
They speak native Airable JSON, distinct from the Frontier JSON adapter in PHP.

The two configured YJ Home units were observed at `10.18.1.181` (Wi-Fi MAC
`f8:70:41:0e:3a:65`) and `10.18.1.166`. These are DHCP observations, not routing
selectors; the exact directory hostname identifies compatible units.

The `cs806-radio` service runs in YJ Home CT 103 and accepts HTTP CONNECT from
the Mihomo gateway on `10.18.0.13:8088`. It terminates the radio's TLS inside
the tunnel, answers `/airable/radios/popular` from `data/radios_2.json`, and
forwards other directory requests to the original host with their method,
path, query, and Authorization intact. Upstream TLS certificates are verified.
The service only accepts CONNECT for the configured Airable host on port 443.
It never logs credentials or forwards them to station stream servers.

## Behavior

- **Internet Radio → Popular stations** displays the shared favorites,
  alphabetically. The JSON list title is `Our favorites`; the device's menu
  label may remain `Popular stations`.
- Every unit using this hostname receives the same list. No per-radio
  registration or copy of the favorites is needed.
- Germany remains the master. The existing five-minute sync updates the
  YJ list; this service reads it on each request, without a cache or restart.
- Local detail/play URLs use a hash of the configured stream URL, so presets
  survive reordering and renaming. Changing a stream URL changes its ID;
  re-save that preset. Unknown native IDs pass through to Airable; removed
  legacy `/local/cs806/` entries return 404.
- Search, locations, and other upstream browsing continue through Airable.
  Local entries omit upstream `actions`: use PRESET to save them on the radio,
  not the upstream cloud-favorites action.
- Entries marked `proxy` use the adapter's stream relay. `nometa` suppresses
  ICY metadata negotiation for AsiaFM. Other entries use the configured stream
  URL directly. The relay follows HTTP redirects and supports HTTPS streams.
- Codec defaults to MP3, with AAC detection for `/aac/`, `.aac`, and AsiaFM's
  extensionless stream. An optional `codec` station field overrides it.

## Station information and artwork

`station-details.json` supplements the shared list by exact stream URL with
verified static Airable fields. 1LIVE has the native place `Cologne`, language
`German`, and slogan `Für den Sektor`. Other stations explicitly clear these
fields to prevent the firmware retaining information from the previous station.
Add verified entries with a source URL; do not infer locations from stream hosts.

These fields are station information, not changing artist/song titles. Observed
CS-806 stream requests send `Icy-MetaData: 0`, including native Airable playback;
dynamic track information is not confirmed on this firmware.

Vendored logos have the native Airable size range: 64, 128, 256, 512, and 1024
pixels. Regenerate with `sh deploy/cs806/generate-logos.sh` (ImageMagick required)
and commit the results. The nginx station-logos bind mount serves them directly.
Upscaling supplies the firmware's requested sizes but does not add image detail.
If any generated variant is absent, the adapter advertises the original logo.

## Routing

The YJ Mihomo template in `infra-configs/proxy-rules/mihomo/yj-janosch-home.yaml`
needs an HTTP proxy named `CS806-Radio` at `10.18.0.13:8088` and, before broad
IP or domain rules, these rules **in this order**:

```yaml
- AND,((SRC-IP-CIDR,10.18.0.13/32),(DOMAIN,5788230443.airable.io)),Proxy
- DOMAIN,5788230443.airable.io,CS806-Radio
```

The first rule keeps the service's own upstream requests on the normal external
proxy; without it they loop back into the adapter. Keep DNS public/fake-IP:
no hostname override, fixed upstream IP, or permanent nft DNAT is needed.
Only this exact observed hostname is intercepted, not all `airable.io` traffic.

## Install

Deploy through git to `/opt/frontier-radio-api` in CT 103, then:

```sh
install -m 0644 deploy/cs806/cs806-radio.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cs806-radio
curl -fsS http://10.18.0.13:8088/health
```

Python 3.11+ and OpenSSL support are the only runtime requirements. The service
runs under a dynamic unprivileged user. Systemd supplies the existing Radio-API
TLS key through a private credential file; do not loosen the key's permissions.
Health verifies that the shared favorites file is readable and valid.

Enable the gateway route after the service is healthy. Verify physical radio
list/detail/play requests using `journalctl -u cs806-radio`, then confirm sound
on the radio. Tests: `python3 -m unittest discover -s deploy/cs806 -v`.

Rollback: remove the two routing rules and proxy through the config pipeline;
new connections return to Airable. Then `systemctl disable --now cs806-radio`.
The Auna/Frontier HTTP/HTTPS endpoints are separate and remain available.

## Protocol diagnosis

Radio, stream and redirect identifiers must have three parts, matching native
Airable responses. Two-part IDs make app `0.43.3.ru` exit Internet Radio to the
main menu. Station location, language and slogan must be present even when
empty, because omitted fields can leave the previous station's text displayed.

`deploy/airable-probe.py` is a temporary transparent HTTP forwarding probe.
Its captures include credentials and must stay in a mode-0700 `/run` directory.
Use a time-limited, source-and-destination-specific DNAT with an independent
rollback timer; never leave diagnostic capture enabled in production. Inspect
only sanitized response shapes. Delete captures when diagnosis is finished.
`adapter.py --direct-tls-port 8443` provides a temporary TLS listener for the
same narrowly scoped DNAT test; production uses CONNECT on 8088 only.
