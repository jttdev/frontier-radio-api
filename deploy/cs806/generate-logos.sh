#!/bin/sh
# Normalize vendored artwork to the image sizes advertised to CS-806 firmware.
set -eu
cd "$(dirname "$0")/../minipc-germany-01/station-logos"
for size in 64 128; do
    mkdir -p "cs806/$size"
    for logo in ./*.png; do
        magick "$logo" -resize "${size}x${size}!" -strip "cs806/$size/${logo##*/}"
    done
done
