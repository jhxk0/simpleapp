#!/bin/bash
# full layout pipeline for one board (kept for compatibility): same as  python3 pipeline.py <board> route
cd "$(dirname "$0")"
exec python3 -u pipeline.py "$1" route "${2:-80}" 1
