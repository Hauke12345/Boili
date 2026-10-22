"""Shared timeline for the explainer: used by the Blender scene and the 2D overlay."""
FPS = 24
END = 1296            # 54 s

# Shots: (start_frame, camera_location, camera_target)  -- world metres, board is 0.965 x 0.62, top at z=0.016
SHOTS = [
    (0,    (0.95, -1.00, 0.80), (0.0, 0.0, 0.03)),     # intro: board three-quarter view
    (120,  (0.30, -1.05, 0.78), (-0.05, 0.0, 0.03)),
    (165,  (-0.62, -0.30, 0.46), (-0.30, 0.12, 0.03)),  # mains input close-up
    (300,  (-0.60, -0.36, 0.48), (-0.28, 0.10, 0.03)),
    (345,  (0.12, -0.62, 0.55), (-0.07, 0.05, 0.08)),   # isolated 5 V supply
    (450,  (0.18, -0.60, 0.52), (0.00, 0.05, 0.06)),
    (495,  (0.42, -0.42, 0.42), (0.25, 0.10, 0.03)),    # 3.3 V regulator + ESP32
    (590,  (0.48, -0.38, 0.40), (0.30, 0.12, 0.03)),
    (640,  (0.62, -0.30, 0.55), (0.33, 0.24, 0.05)),    # antenna / WiFi
    (780,  (0.58, -0.32, 0.52), (0.30, 0.22, 0.05)),
    (825,  (0.16, -0.50, 0.66), (-0.02, -0.20, 0.03)),  # relay driver
    (930,  (0.08, -0.55, 0.70), (-0.10, -0.20, 0.03)),
    (1000, (-0.40, -2.70, 1.55), (-0.85, 0.0, 0.50)),   # system view: contactor + tank
    (1050, (-0.48, -2.75, 1.58), (-0.85, 0.0, 0.52)),
    (1095, (0.0, -0.10, 1.42), (0.0, 0.0, 0.0)),         # top-down safety view
    (1175, (0.0, -0.12, 1.38), (0.0, 0.0, 0.0)),
    (1215, (-0.30, -3.10, 1.75), (-0.80, 0.0, 0.50)),   # outro
    (1296, (-0.15, -3.30, 1.85), (-0.78, 0.0, 0.50)),
]

# Net flow animations: (net, source pad, start frame, colour)
LIVE = (1.0, 0.22, 0.04)
NEUT = (0.10, 0.40, 1.00)
V5 = (1.0, 0.78, 0.08)
V33 = (0.10, 0.95, 0.80)
SIG = (0.85, 0.25, 1.00)
FLOWS = [
    ("/L_IN", "J1.1", 175, LIVE),
    ("/N", "J1.2", 190, NEUT),
    ("/L_F", "F1.2", 215, LIVE),
    ("+5V", "PS1.4", 370, V5),
    ("+3V3", "U1.2", 505, V33),
    ("/STATUS_LED", "U2.10", 560, (0.2, 1.0, 0.3)),
    ("/LED_K2", "R6.2", 570, (0.2, 1.0, 0.3)),
    ("/HEAT_EN", "U2.11", 840, SIG),
    ("/GATE", "R3.2", 868, SIG),
    ("/RELAY_DRV", "Q1.3", 885, SIG),
    ("/LED_K1", "R5.2", 905, (1.0, 0.1, 0.05)),
    ("/L_SW", "K1.3", 930, LIVE),
]
FLOW_SPEED_MM_PER_FRAME = 1.6
HEAT_OFF = 1190            # cheap hours over: control nets fade out
RELAY_ON = 912
CONTACTOR_ON = 975
TANK_HEAT = (990, 1190)
WIFI = (650, 790)
STATUS_BLINK_FROM = 575
ISOLATION = (1100, 1185)

# 2D labels anchored to 3D points: id -> (text, world point, first frame, last frame)
LABELS = {
    "mains":   ("230 V in (L, N)",          (-0.455, 0.13, 0.06), 185, 330),
    "fuse":    ("Fuse T1A",                 (-0.297, 0.214, 0.10), 200, 330),
    "mov":     ("Surge protector",          (-0.337, 0.09, 0.09), 225, 330),
    "psu":     ("HLK-PM01: 230 V -> 5 V\n(isolated)", (-0.07, 0.06, 0.17), 360, 485),
    "reg":     ("3.3 V regulator",          (0.177, 0.01, 0.04), 515, 615),
    "esp":     ("ESP32 (WiFi)",             (0.358, 0.10, 0.05), 525, 640),
    "ledg":    ("Status LED",               (0.138, -0.20, 0.03), 580, 640),
    "antenna": ("Antenna",                  (0.358, 0.27, 0.05), 660, 790),
    "q1":      ("Transistor drives relay",  (-0.003, -0.26, 0.03), 872, 935),
    "relay":   ("Relay switches\ncontactor coil", (-0.17, -0.19, 0.17), 925, 995),
    "ledr":    ("Heating LED",              (0.028, -0.17, 0.03), 935, 995),
    "contactor": ("Contactor",              (-1.05, -0.30, 0.42), 1005, 1085),
    "tank":    ("Water heater",             (-1.75, 0.10, 1.05), 1005, 1085),
    "thermo":  ("Thermostat + limiter\nstay in series", (-1.60, -0.17, 0.48), 1020, 1085),
    "mainsside": ("230 V side",             (-0.30, -0.05, 0.03), 1110, 1185),
    "lvside":  ("Low-voltage side",         (0.25, -0.05, 0.03), 1110, 1185),
}

# Captions: (text, first, last)
CAPTIONS = [
    ("Spot-price water heater controller", 15, 150),
    ("230 V enters through a fuse and a surge protector", 180, 335),
    ("An isolated module turns 230 V into safe 5 V", 350, 488),
    ("A regulator makes 3.3 V and the ESP32 wakes up", 500, 635),
    ("Over WiFi it fetches tomorrow's Nord Pool spot prices", 650, 820),
    ("Cheapest hour: the ESP32 switches the relay on", 835, 995),
    ("The relay energises the contactor, which powers the heater", 1000, 1090),
    ("At least 6 mm between 230 V and the low-voltage side", 1100, 1190),
    ("Heats the water when electricity is cheapest", 1236, 1296),
]

# Price chart (c/kWh) for the 24 hours of "tomorrow"
PRICES = [6.1, 5.2, 4.3, 3.9, 4.1, 4.6, 7.8, 12.4, 15.1, 13.2, 9.8, 8.1,
          7.2, 6.9, 7.5, 9.4, 12.8, 16.9, 18.2, 14.5, 10.1, 8.2, 6.4, 5.5]
CHEAP_HOURS = sorted(sorted(range(24), key=lambda h: PRICES[h])[:4])   # 2,3,4,5
CHART = (690, 1095)        # chart visible
# clock (hour as float) keyframes for the chart cursor
CLOCK = [(690, 23.0 - 24), (820, 1.5), (912, 2.0), (1095, 3.4)]
OUTRO_CLOCK = [(1180, 5.55), (1200, 6.0), (1245, 6.4)]
CHART_OUTRO = (1180, 1242)
