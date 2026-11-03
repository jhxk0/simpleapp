#!/bin/bash
# full layout pipeline for one board: place -> DSN -> Freerouting x2 -> SES -> pours/stitching -> DRC
set -e
B=$1; PASSES=${2:-80}
cd "$(dirname "$0")"; T=$PWD
FR="/usr/lib/jvm/java-25-openjdk-amd64/bin/java -jar /home/user/tools/freerouting-2.4.1-executable.jar --gui.enabled=false"
k9 python3 pcbgen.py $B 2>&1 | tail -1
k9 python3 route.py $B fanout 2>&1 | grep -v 'assert\|leak' | tail -1
for pass in 1 2; do
  k9 python3 route.py $B dsn | tail -1
  (cd ../$B && rm -f $B.ses && $FR -de $B.dsn -do $B.ses -mp $PASSES -mt 4 > fr$pass.log 2>&1)
  grep -o "final score: [^)]*)" ../$B/fr$pass.log | tail -1
  k9 python3 route.py $B ses | tail -1
done
k9 python3 route.py $B finish 2>&1 | grep -v 'assert\|leak' | tail -5
python3 drc.py $B 30
