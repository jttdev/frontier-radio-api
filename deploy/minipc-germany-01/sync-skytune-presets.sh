#!/bin/bash
# Push the shared favorites onto a Skytune-firmware radio.
#
# Skytune radios have no directory portal to redirect: they keep their
# favorites in a device-local "My Favourite" preset list, editable over
# HTTP at the radio's own address. This script mirrors the shared
# Radio-API list into that store, sorted case-insensitively by name
# because the device shows the presets in stored order.
#
# Stations flagged proxy in the shared list are pointed at Radio-API's
# stream endpoint so TLS termination and ICY-metadata stripping still
# apply; the rest get their direct stream URL, exactly as the Frontier
# radios fetch them.
#
# Usage: sync-skytune-presets.sh <radio-ip> <mediayou-serial>
set -euo pipefail

RADIO_IP="${1:?usage: $0 <radio-ip> <mediayou-serial>}"
SERIAL="${2:?usage: $0 <radio-ip> <mediayou-serial>}"
DATA="$(dirname "$(readlink -f "$0")")/data/radios_2.json"
BASE="http://10.3.0.12"
CGI="http://${RADIO_IP}/cgi-bin/EN/cgi"

[ -r "$DATA" ] || { echo "no shared station list at $DATA" >&2; exit 1; }

# name<TAB>url, ordered case-insensitively by name. The station ID is the
# index in the stored list plus 1000, so it is read before sorting.
mapfile -t ROWS < <(python3 - "$DATA" "$SERIAL" "$BASE" <<'PY'
import json, sys
data, serial, base = sys.argv[1], sys.argv[2], sys.argv[3]
rows = []
for index, station in enumerate(json.load(open(data))):
    if station.get("category") not in ("Favoriten", "Favorites"):
        continue
    url = (f"{base}/mediayou.php?action=stream&id={index + 1000}&serial={serial}"
           if station.get("proxy") else station["url"])
    rows.append((station["name"], url))
for name, url in sorted(rows, key=lambda r: r[0].casefold()):
    print(f"{name}\t{url}")
PY
)

[ "${#ROWS[@]}" -gt 0 ] || { echo "shared list has no favorites" >&2; exit 1; }

count_presets() {
	curl -sS --max-time 10 "${CGI}?CL=0" | grep -c "name='name' value=" || true
}

# Deleting index 0 shifts the rest up, so the list empties by repetition.
existing="$(count_presets)"
for ((i = 0; i < existing; i++)); do
	curl -sS --max-time 15 -o /dev/null "${CGI}?CD=0;CI=0"
done

remaining="$(count_presets)"
[ "$remaining" -eq 0 ] || { echo "radio still holds $remaining presets" >&2; exit 1; }

index=0
for row in "${ROWS[@]}"; do
	name="${row%%$'\t'*}"
	url="${row#*$'\t'}"
	code="$(curl -sS --max-time 15 -o /dev/null -w '%{http_code}' \
		--data-urlencode "channel_name=${name}" \
		--data-urlencode "channel_url=${url}" \
		"${CGI}?CA=0;CI=${index}")"
	[ "$code" = 200 ] || { echo "add failed (${code}): ${name}" >&2; exit 1; }
	printf '%3d. %s\n' "$((index + 1))" "$name"
	index=$((index + 1))
done

final="$(count_presets)"
[ "$final" -eq "${#ROWS[@]}" ] ||
	{ echo "expected ${#ROWS[@]} presets, radio reports $final" >&2; exit 1; }
echo "${final} presets synced to ${RADIO_IP}"
