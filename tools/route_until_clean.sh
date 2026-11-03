#!/bin/bash
# place + fanout once, then route (2 Freerouting passes) up to N attempts until DRC has zero errors
B=$1; PASSES=${2:-80}; TRIES=${3:-4}
cd "$(dirname "$0")"
FR="/usr/lib/jvm/java-25-openjdk-amd64/bin/java -jar /home/user/tools/freerouting-2.4.1-executable.jar --gui.enabled=false"
k9 python3 pcbgen.py $B 2>&1 | tail -1
k9 python3 route.py $B fanout 2>&1 | grep -v 'assert\|leak' | tail -1
cp ../$B/$B.kicad_pcb ../$B/$B.fanout.kicad_pcb
for t in $(seq 1 $TRIES); do
  echo "--- attempt $t"
  cp ../$B/$B.fanout.kicad_pcb ../$B/$B.kicad_pcb
  for pass in 1 2; do
    k9 python3 route.py $B dsn 2>&1 | grep -v 'assert\|leak' | tail -1
    (cd ../$B && rm -f $B.ses && $FR -de $B.dsn -do $B.ses -mp $PASSES -mt 4 > fr$pass.log 2>&1)
    grep -o "final score: [^)]*)" ../$B/fr$pass.log | tail -1
    k9 python3 route.py $B ses 2>&1 | grep -v 'assert\|leak' | tail -1
  done
  k9 python3 route.py $B finish 2>&1 | grep -v 'assert\|leak' | tail -4
  if python3 drc.py $B 20; then echo "CLEAN on attempt $t"; cp ../$B/$B.kicad_pcb ../$B/$B.clean.kicad_pcb; break; fi
done
rm -f ../$B/$B.fanout.kicad_pcb
