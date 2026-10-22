# Boili enclosure: production notes (rev A)

Two-part injection-moulded enclosure for the Boili controller PCB (96.5 × 62 mm).
Modelled in FreeCAD 1.0 (Part workbench, scripted).

## Files
| File | Content |
|---|---|
| `spot_heater_enclosure.FCStd` | FreeCAD document: base, lid, light pipes, gasket, glands, screws, the populated PCB, and a `Parameters` sheet |
| `spot_heater_base.step`, `spot_heater_lid.step` | Moulded parts, send these to the toolmaker |
| `spot_heater_lightpipes.step`, `spot_heater_gasket.step` | Secondary parts |
| `spot_heater_cableglands.step`, `spot_heater_screws.step` | Purchased parts, simplified, for fit only |
| `spot_heater_enclosure_assembly.step` | Everything assembled |
| `housing.py` | Parametric source: change the parameters at the top and re-run with FreeCAD's Python |
| `fit_report.json` | Automated interference and clearance check |

## Key data
- **Outside size:** 133 × 95 × 33 mm including the wall ears. The body alone is 133 × 73 × 33 mm.
- **Material:** PC/ABS, UL94 V-0 at 2.5 mm (e.g. Covestro Bayblend FR3010), grey RAL 7016 base and light grey lid. Mains equipment needs a V-0 flame rating.
- **Mass:** base about 63 g, lid about 33 g.
- **Walls:** 2.5 mm nominal. Ribs are 1.5 mm (60 % of the wall) to avoid sink marks.
- **Draft:** 1° on all walls parallel to the pull direction. The texture should be MT-11010 or finer, which works at 1°.
- **Parting line:** at the base rim and the lid's skirt bottom. Both parts eject straight with no side actions, except the two gland holes (see below).

## Sealing and assembly
- The base rim has a 1.2 × 2 mm tongue that enters a 1.8 × 3 mm groove in the lid. A Ø1.6 mm TPE/EPDM cord gasket sits in the groove. **Target IP54** (indoor technical room).
- 4 × ST3.5 × 16 self-tapping screws for plastics (e.g. EJOT PT K35×16) go into Ø2.8 holes in the Ø8 screw towers. Use screws with an under-head O-ring, because the screw holes sit inside the seal line.
- The PCB is held by 4 × PT K25×6 screws in Ø2.3 holes on 6 mm stand-offs.
- 2 × M16 × 1.5 cable glands (IP68, cable 4–8 mm) go in the left wall: mains in, and the contactor coil out.
  - Mould the holes with a side core, or mould them as 0.6 mm knock-outs and drill afterwards.
  - The inside lock-nut seats against the 1° drafted wall. This is fine for standard glands; for a perfectly flat seat, add a 0.5 mm spot-face.
- 4 slotted wall ears for Ø4 screws, gusseted.

## User interface
- 2 × Ø3 clear PC light pipes, press-fitted in moulded holder tubes, carry the HEAT and STATUS LEDs to the lid.
- **BOOST** is a moulded cantilever button in the lid (a 1.6 mm living flex tongue with a plunger 1 mm above SW2). The U-slot is covered by the front overlay label (polyester, 0.2 mm, with adhesive), which also keeps the IP rating.
- Embossed 0.4 mm graphics: SPOT HEATER, the 230 V~ hazard triangle over the mains bay, and the LED and button labels.

## Verified in CAD (`fit_report.json`)
- Interference with every PCB component: **0.000 mm³** for the base, lid and glands.
- The lid ribs clear the tallest parts (the power module and relay) by 2.1 mm. The solder pins clear the floor by 2.7 mm.
- All solids are valid.

## Before tooling
- Run a mould-flow analysis on PC/ABS. I suggest a gate in the base floor centre and a gate in the lid underside centre.
- Make 3D-printed prototypes (SLA or MJF) to check the gasket compression, flex-button feel and gland fit.
- Electrical safety (EN 60335-1 / EN 62368-1):
  - Keep internal wiring routed in the wiring bay.
  - Confirm the 6 mm creepage on the PCB.
  - Confirm the plastic's glow-wire rating (GWIT 775 °C) for unattended appliances.
