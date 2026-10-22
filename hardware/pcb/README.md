# Boili PCB: spot-price water heater controller (rev 1.0)

ESP32 board that turns a water heater's contactor on during the cheapest electricity hours.
It fetches Nord Pool spot prices over WiFi and switches the **contactor coil**, never the heater itself.
The tank's own thermostat and over-temperature limiter stay in series with the heater element.

KiCad 9 project. ERC: 0 errors / 0 warnings. DRC: 0 violations, 0 unconnected, schematic parity OK.
SPICE checks (relay driver, boot, supply rails, power-up) are in [`simulation/`](simulation).

## Files
| Path | What |
|---|---|
| `spot_heater.kicad_pro / .kicad_sch / .kicad_pcb` | The KiCad project |
| `spot_heater.kicad_dru` | Custom rule: 6 mm clearance **and** creepage between mains and low-voltage copper |
| `fab/` | Gerbers, drill file and pick-and-place file, ready to upload to a PCB fab |
| `docs/` | Schematic PDF, PCB top/bottom PDFs, 3D render, BOM (CSV) |

## Board
- 96.5 × 62 mm, 2 layers, 1.6 mm FR-4, 4 × M3 holes.
- Minimum drill 0.2 mm (the ESP32 module's ground-pad vias). Standard at most fabs, sometimes a small surcharge.
- Mains section on the left, low-voltage section on the right. A ground plane on the bottom layer covers only the low-voltage side.
- Mains tracks are 1.5 mm wide with 2 mm clearance between L and N.

## How it works
`J1` (230 VAC in) → `F1` T1A fuse → `RV1` varistor (surge protection) → `PS1` HLK-PM01 makes isolated 5 V → `U1` regulates to 3.3 V for the ESP32.
`IO26` drives `Q1`, which energises relay `K1`. `K1` connects fused L to `J2` and on to the contactor coil.
`R4` keeps the relay off while the ESP32 boots or resets.

| ESP32 pin | Function |
|---|---|
| IO26 | Heater enable (high = relay on) |
| IO25 | Status LED (green) |
| IO0 | BOOT button. After boot, use it as a manual "boost" button (active low) |
| IO4 | Optional DS18B20 on J4 (4.7 k pull-up fitted) |
| TXD0 / RXD0 | Programming header J3 |

## Wiring (by a qualified electrician)
- **J1:** L and N from a protected circuit.
- **J2:** to the contactor coil A1 (L_SW) and A2 (N). Use a 230 VAC coil contactor rated for the heater (e.g. 3-pole, 25 A, AC-1).
- Heater power goes through the contactor's main contacts and the tank thermostat/limiter, never through this board.
- K1 is rated far above a contactor coil's current. An RC snubber across the coil, often sold as an accessory for the contactor, reduces relay contact wear.
- Mount the board in a closed plastic enclosure.

## Programming
Connect a **3.3 V** USB-UART adapter to J3 (1=3V3, 2=GND, 3=TX, 4=RX, 5=EN, 6=IO0) **with mains disconnected**. Hold BOOT, tap RESET, then flash. After that, update over WiFi (OTA).

## Design choices
- **Relay:** Omron G5Q-1A. Its coil and contact pins sit at opposite ends of the relay, about 8 mm apart. On the G5LE the common contact sits between the coil pins.
- **Isolation:** the mains section and the HLK module's input are kept at least 6 mm from all low-voltage copper. This is checked by DRC, not just by eye.
- **Pins:** the relay and LED pins avoid the ESP32 strapping pins, so boot behaviour is unaffected.
- **Antenna:** the module antenna sits at the board edge with the footprint's copper keep-out respected.
- **Firmware fallback:** decide in firmware what happens without WiFi or prices. A fixed night schedule is suggested.
