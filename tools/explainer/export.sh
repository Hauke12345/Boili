set -e
O="--user-origin 148.25x131mm"
cd /home/claude/spot_heater
k9 kicad-cli pcb export glb $O --subst-models --include-tracks --include-pads --include-zones --include-silkscreen --include-soldermask -o /work/anim/board.glb spot_heater.kicad_pcb | tail -1
for n in /L_IN /L_F /N /L_SW +5V +3V3 GND /HEAT_EN /GATE /RELAY_DRV /LED_K1 /STATUS_LED /LED_K2; do
  f=$(echo $n | tr -d '/+' ); 
  k9 kicad-cli pcb export glb $O --no-board-body --no-components --include-tracks --include-pads --net-filter "$n" -o /work/anim/net_$f.glb spot_heater.kicad_pcb >/dev/null 2>&1 && echo "net $n ok"
done
