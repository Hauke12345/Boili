"""Boili PCB SPICE checks (ngspice 42). Generates decks, runs them, collects measurements and plots."""
import subprocess, os, itertools, json, re
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)

def run(name, body, meas):
    deck = f"* {name}\n.include {HERE}/models.lib\n{body}\n.control\nset filetype=ascii\nrun\n{meas}\n.endc\n.end\n"
    p = os.path.join(OUT, name + ".cir"); open(p, "w").write(deck)
    r = subprocess.run(["ngspice", "-b", p], capture_output=True, text=True, timeout=600)
    log = r.stdout + r.stderr; open(os.path.join(OUT, name + ".log"), "w").write(log)
    vals = {}
    for m in re.finditer(r"^(\w+)\s*=\s*([-+0-9.eE]+)", log, re.M):
        vals[m.group(1).lower()] = float(m.group(2))
    if "error" in log.lower() and not vals:
        print(log[-2000:])
    return vals

def wr(fn, *vecs):
    return f"wrdata {OUT}/{fn} " + " ".join(vecs)

results = {}

# ------------------------------------------------------------------ 1. relay driver corners
# GPIO26 high from 1 ms to 41 ms. ESP32 VOH min = 0.8*VDD = 2.64 V; ~16 Ohm source at 40 mA (40 mA drive spec).
corners = []
for voh, vt, kp, v5, lc in [
        (3.30, 1.05, 80, 5.00, 0.2),    # nominal
        (2.64, 1.45, 25, 4.75, 0.2),    # worst: weak GPIO, max VGS(th), weak FET, low 5 V
        (2.64, 1.45, 25, 4.75, 0.05),
        (2.64, 1.45, 25, 4.75, 0.5),
        (3.30, 0.65, 80, 5.10, 0.5)]:   # fast FET, high 5 V, big coil inductance -> worst flyback
    name = f"relay_voh{voh}_vt{vt}_kp{kp}_v{v5}_L{lc}"
    body = f"""
V5 v5 0 {v5}
Vg g 0 PULSE(0 {voh} 1m 20n 20n 40m 100m)
Rgpio g heat_en 16
X1 v5 heat_en 0 DRIVER VT={vt} KP={kp} LCOIL={lc}
.tran 1u 80m 0 1u
"""
    meas = f"""
let vcoil = v(v5) - v(x1.drv)
meas tran vcoil_on  avg vcoil from=35m to=40m
meas tran vds_on    avg v(x1.drv) from=35m to=40m
meas tran icoil_on  avg i(v5) from=35m to=40m
meas tran vgate_on  avg v(x1.gate) from=35m to=40m
meas tran vdrv_pk   max v(x1.drv) from=41m to=80m
meas tran ton_75    when vcoil=3.75 rise=1
meas tran trel      when i(v.x1.xk1.vsns)=0.002 fall=1 from=41m
meas tran vds_turnon max v(x1.drv) from=1.001m to=1.2m
{wr(name + '.dat', 'v(x1.drv)', 'v(x1.gate)', 'i(v.x1.xk1.vsns)')}
"""
    v = run(name, body, meas)
    v.update(voh=voh, vt=vt, kp=kp, v5=v5, L=lc); corners.append(v)
    print(name, {k: round(x, 5) for k, x in v.items() if isinstance(x, float)})
results["relay_corners"] = corners

# ------------------------------------------------------------------ 2. boot: GPIO26 floating (high-Z, ie=0, no pull) with pad leakage
boot = []
for ileak in (1e-6, -1e-6, 10e-6):
    body = f"""
V5 v5 0 5
Ileak 0 heat_en {ileak}
X1 v5 heat_en 0 DRIVER VT=0.65 KP=80 LCOIL=0.2
.tran 10u 20m
"""
    v = run(f"boot_leak_{ileak}", body, "meas tran vgate max v(x1.gate) from=10m to=20m\nmeas tran icoil max i(v5) from=10m to=20m")
    v["ileak"] = ileak; boot.append(v); print("boot", v)
results["boot"] = boot

# ------------------------------------------------------------------ 3. supply rails: WiFi TX bursts + relay switching
# HLK-PM01: 5.0 V +-0.1 V, 0.6 A cont. (1 A short), ~0.1 V droop at 0.6 A (lygte-info review) -> 0.167 Ohm;
#   internal output capacitance and loop speed are NOT published -> L/C network, C swept.
# AMS1117-3.3: dropout 1.1 V typ / 1.3 V max @ 0.8 A, 5 mA quiescent. Behavioural: Vout = min(3.3, Vin - Vdo(I)),
#   first-order loop (tau swept). Does NOT model AMS1117 stability with ceramic caps (no vendor model).
# Caps with DC-bias derating: C1 22u/10V 1206 @5 V ~ 11 uF, C2 22u @3.3 V ~ 14 uF, C3 10u 0805 @3.3 V ~ 6 uF,
#   C4 100n, module-internal ~10 uF -> ~7 uF.
# ESP32 load: 80 mA base + TX bursts (datasheet: 802.11b 19.5 dBm peak 379 mA; Espressif asks for >= 0.5 A supply).
rails = []
for ipk, cint, tau, vset in [(0.379, 220e-6, 1e-6, 5.0), (0.379, 220e-6, 2e-6, 5.0), (0.5, 100e-6, 2e-6, 4.9), (0.5, 100e-6, 5e-6, 4.9), (0.5, 47e-6, 10e-6, 4.9)]:
    gm = 0.5 * 34e-6 / tau          # loop crossover ~ half the error-amp pole with the nominal 34 uF
    name = f"rails_ipk{ipk}_cint{cint*1e6:.0f}u_tau{tau*1e6:.0f}u_v{vset}"
    body = f"""
* HLK-PM01 output
Vhlk hs 0 {vset + 0.03}
Rhlk hs h1 0.167
Lhlk h1 hint 20u
Cint hint ci {cint}
Resr ci 0 0.08
Rtr hint v5 0.01
* board 5 V: C1
C1 v5 c1e 11u
R1e c1e 0 0.005
* relay driver switches on at 6 ms (during a TX burst) and off at 14 ms
Vg g 0 PULSE(0 3.3 6m 20n 20n 8m 100m)
X1 v5 g 0 DRIVER VT=1.05 KP=80 LCOIL=0.2
* AMS1117 behavioural: PI error amp with first-order bandwidth tau, pass current clamped by
* current limit (1.1 A) and dropout (0.85 V + 0.35 Ohm -> 1.13 V @ 0.8 A, datasheet 1.1 V typ)
Berr e0 0 V = 3.3 - v(v33)
Rlp e0 e1 1k
Clp e1 0 {tau / 1e3}
Gint 0 eint cur = v(e1) / {10 * tau}
Cint2 eint 0 1
Gpass v5 v33 cur = max(0, min(1.1, min({gm} * (v(e1) + v(eint)), max(0, (v(v5) - v(v33) - 0.85) / 0.35))))
Iq v5 0 0.005
* 3V3 caps: C2, C3, C4, module-internal
C2 v33 c2e 14u
R2e c2e 0 0.005
C3 v33 c3e 6u
R3e c3e 0 0.006
C4 v33 0 100n
Cmod v33 cme 7u
Rme cme 0 0.01
* ESP32 load: base + TX bursts (1.6 ms on / 4 ms period, 1 us edges)
Iesp v33 0 PULSE(0.08 {ipk} 2m 1u 1u 1.6m 4m)
.ic v(v33)=3.3 v(v5)={vset} v(eint)={0.085 / gm} v(e1)=0 v(hint)={vset}
.tran 0.5u 20m 0 0.5u
"""
    meas = f"""
meas tran v33_min  min v(v33) from=1m to=20m
meas tran v5_min   min v(v5) from=1m to=20m
meas tran hdr_min  min par('v(v5)-v(v33)') from=1m to=20m
meas tran ihlk_min min i(Vhlk) from=1m to=20m
meas tran ihlk_avg avg i(Vhlk) from=2m to=18m
meas tran v33_avg  avg v(v33) from=2m to=18m
meas tran v33_max  max v(v33) from=2m to=20m
{wr(name + '.dat', 'v(v5)', 'v(v33)', 'i(Vhlk)')}
"""
    v = run(name, body, meas)
    for k in ("ihlk_max", "ihlk_avg"):
        if k in v: v[k] = -v[k]
    if "ihlk_min" in v: v["ihlk_peak"] = -v.pop("ihlk_min")
    v.update(ipk=ipk, cint=cint, tau=tau, vset=vset); rails.append(v)
    print(name, {k: round(x, 4) for k, x in v.items() if isinstance(x, float)})
results["rails"] = rails

# ------------------------------------------------------------------ 4. power-up: HLK ramps in ~3 ms, LDO follows, EN RC (R1 10k / C5 1 uF)
body = """
Vhlk hs 0 PWL(0 0 0.5m 0 3.5m 5.03)
Rhlk hs h1 0.167
Lhlk h1 hint 20u
Cint hint 0 220u
Rtr hint v5 0.01
C1 v5 0 11u
Btgt tgt 0 V = max(0, min(3.3, v(v5) - 0.95))
Rlp tgt lp 1k
Clp lp 0 2n
Eldo oi 0 lp 0 1
Rout oi v33 0.02
C2 v33 0 14u
C3 v33 0 6u
Cmod v33 0 7u
Iesp v33 0 PWL(0 0 1m 0 1.0001m 0.02)
R1 v33 en 10k
C5 en 0 1u
* GPIO26 high-Z during power-up (worst +1 uA leakage into the node)
Ileak 0 heat_en 1u
X1 v5 heat_en 0 DRIVER VT=0.65 KP=80 LCOIL=0.2
.tran 5u 60m
"""
meas = f"""
meas tran t_v33ok when v(v33)=3.0 rise=1
meas tran t_en    when v(en)=2.475 rise=1
meas tran vgate_max max v(x1.gate)
meas tran icoil_max max i(Vhlk)
{wr('powerup.dat', 'v(v5)', 'v(v33)', 'v(en)', 'v(x1.gate)')}
"""
v = run("powerup", body, meas); print("powerup", v); results["powerup"] = v

json.dump(results, open(os.path.join(HERE, "results.json"), "w"), indent=1)
