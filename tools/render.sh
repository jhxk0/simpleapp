#!/bin/bash
# render.sh <board_dir> <board> <outprefix>  -> PNGs of top and bottom layer stacks
set -e
cd "$1"
k9 kicad-cli pcb export svg --mode-single --exclude-drawing-sheet --fit-page-to-board \
  --layers F.Cu,F.Silkscreen,F.Courtyard,Edge.Cuts -o "$3_top.svg" "$2.kicad_pcb" >/dev/null
k9 kicad-cli pcb export svg --mode-single --exclude-drawing-sheet --fit-page-to-board --mirror \
  --layers B.Cu,B.Silkscreen,B.Courtyard,Edge.Cuts -o "$3_bot.svg" "$2.kicad_pcb" >/dev/null
for s in top bot; do echo "<html><body style='margin:0;background:#151515'><img src='$(basename $3)_$s.svg' style='width:880px;height:880px;object-fit:contain;margin:10px'></body></html>" > "$3_$s.html"; done
node -e '
const {chromium}=require("playwright");
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:900,height:900}});
for (const s of ["top","bot"]){const f=process.argv[1]+"_"+s;
 await p.goto("file://"+process.cwd()+"/"+f+".html"); await p.waitForTimeout(300);
 await p.screenshot({path:f+".png"});}
await b.close();})();' "$3"
rm -f "$3"_top.html "$3"_bot.html
