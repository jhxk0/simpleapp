#!/bin/bash
# place + fanout once, then route (2 Freerouting passes) up to N attempts until DRC has zero errors
# (same as: python3 pipeline.py <board> route <passes> <tries>)
cd "$(dirname "$0")"
exec python3 -u pipeline.py "$1" route "${2:-80}" "${3:-4}"
