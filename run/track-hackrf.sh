#!/bin/bash

BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

cd /local/franc/franc-master-control/build/bin

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <callsign>"
    exit 1
fi

# the callsign is passed as an argument
CALLSIGN=$1

# Grab location from APRS messaging GPS
MSG=$(/local/franc/franc-master-control/run/aprs-msg.py)
echo $MSG

# Generate PCM Audio and play it
/local/franc/franc-master-control/build/bin/FRANC -c $CALLSIGN -o pkt.pcm -f pcm $MSG
play -r 48000 -c 1 -t raw -e floating-point -b 32 pkt.pcm

# Generate IQ File and send to HackRF
/local/franc/franc-master-control/build/bin/FRANC -c $CALLSIGN -o pkt.s8 -f s8 $MSG
hackrf_transfer -f 144390000 -s 2400000 -t pkt.s8 -a 1 -x 40

# Delete generated files
rm -rf pkt.cpm
rm -rf pkt.s8
