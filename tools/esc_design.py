"""4-in-1 ESC, 3-6S, 30.5mm mount.

Per channel: STM32G071K8U6N running AM32, pin-compatible with AM32 target JUPITER_80_G071
(HARDWARE_GROUP_G0_L, current ADC PA4, voltage ADC PA5, TARGET_VOLTAGE_DIVIDER 285), 3x LM2105
half-bridge drivers, 6x CSD18543Q3A (60V 8.1mOhm). Board-level: 2x 10V gate-drive LDOs. No total-current
sensor: FC connector pin 3 (CURR) is not connected.
"""
from design import Design

d = Design("esc", "Drone 4-in-1 ESC (AM32, G071)")
GND = "GND"
FET = "Transistor_FET:CSD18543Q3A"
FET_FP = "Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET"

# ---------------------------------------------------------------- shared power
d.group("Battery & sense")
PADBIG = "Connector_Wire:SolderWirePad_1x01_SMD_5x10mm"
# battery pads feed the VBAT / GND planes directly through via arrays (no shunt in the power path)
d.add("TP", "Connector:TestPoint", "BAT+", PADBIG, {"1": "VBAT"},
      note="also solder the low-ESR bulk electrolytic (35V, 470-1000uF) across BAT+/BAT- - mandatory")
d.add("TP", "Connector:TestPoint", "BAT-", PADBIG, {"1": GND})
for _ in range(4):
    d.C("10uF", "VBAT", GND, size="1206", volt="50V", lcsc="", lcsc_ok=False)
d.flag("VBAT"); d.flag(GND)

d.group("Gate drive supply")
for rail in ("A", "B"):        # A feeds ESC1+2, B feeds ESC3+4
    d.R("22", "VBAT", "VFILT_" + rail, size="0603")
    d.C("1uF", "VFILT_" + rail, GND, size="0805", volt="50V", lcsc="", lcsc_ok=False)
    d.flag("VFILT_" + rail)
    d.add("U", "Regulator_Linear:L78L10_SOT89", "L78L10", "Package_TO_SOT_SMD:SOT-89-3",
          {"3": "VFILT_" + rail, "2": GND, "1": "+10V_" + rail}, mpn="L78L10ACUTR")
    d.C("1uF", "+10V_" + rail, GND, size="0603", volt="25V", lcsc="", lcsc_ok=False)

d.group("FC connector")
d.add("J", "Connector_Generic:Conn_01x08", "FC",
      "Connector_JST:JST_SH_SM08B-SRSS-TB_1x08-1MP_P1.00mm_Horizontal",
      {"1": "VBAT", "2": GND, "4": "TLM", "5": "SIG1", "6": "SIG2", "7": "SIG3", "8": "SIG4"},
      mpn="SM08B-SRSS-TB")
d.add("TP", "Connector:TestPoint", "TLM", "TestPoint:TestPoint_Pad_1.0x1.0mm", {"1": "TLM"},
      note="not driven; AM32 RPM telemetry uses bidirectional DShot on SIGn")

# ---------------------------------------------------------------- 4 channels
for n in (1, 2, 3, 4):
    p = "E%d_" % n
    rail = "+10V_A" if n <= 2 else "+10V_B"
    v33 = "+3V3_%d" % n
    d.group("ESC%d MCU" % n)
    d.add("U", "MCU_ST_STM32G0:STM32G071K8UxN", "STM32G071K8U6N",
          "Package_DFN_QFN:QFN-32-1EP_5x5mm_P0.5mm_EP3.45x3.45mm",
          {"VDD": v33, "VSS": GND,
           "PA10/UCPD1_DBCC2": p + "HA", "PA9/UCPD1_DBCC1": p + "HB", "PA8": p + "HC",
           "PB15": p + "LA", "PB0": p + "LB", "PA7": p + "LC",
           "PC6": p + "SIG",
           "PA0": p + "BEMF_A", "PA2": p + "BEMF_B", "PB7": p + "BEMF_C",
           "PA1": p + "NEUTRAL", "PA3": p + "NEUTRAL",
           "PA4": GND, "PA5": p + "VSENSE",              # PA4 = current ADC: no sensor, tied low
           "PA13": p + "SWDIO", "PA14": p + "SWCLK"},
          mpn="STM32G071K8U6N", note="AM32 target JUPITER_80_G071 pinout")
    d.add("U", "Regulator_Linear:MCP1703Ax-330xxTT", "MCP1703-3.3", "Package_TO_SOT_SMD:SOT-23",
          {"3": rail, "1": GND, "2": v33}, mpn="MCP1703AT-3302E/CB")
    d.C("1uF", rail, GND, size="0603", volt="25V", lcsc="", lcsc_ok=False)
    d.C("1uF", v33, GND)
    d.C("100nF", v33, GND)
    d.R("100", "SIG%d" % n, p + "SIG")
    d.R("27.4k", "VBAT", p + "VSENSE"); d.R("1k", p + "VSENSE", GND)   # x28.4 (target 28.5)
    d.add("TP", "Connector:TestPoint", "DIO%d" % n, "TestPoint:TestPoint_Pad_1.0x1.0mm", {"1": p + "SWDIO"})
    d.add("TP", "Connector:TestPoint", "CLK%d" % n, "TestPoint:TestPoint_Pad_1.0x1.0mm", {"1": p + "SWCLK"})
    d.add("TP", "Connector:TestPoint", "3V3_%d" % n, "TestPoint:TestPoint_Pad_1.0x1.0mm", {"1": v33})

    d.group("ESC%d power stage" % n)
    for ph in "ABC":
        P_ = p + "PH_" + ph
        d.add("U", "Driver_FET:LM2105DSG", "LM2105", "Package_SON:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm",
              {"1": rail, "4": GND, "9": GND, "2": p + "H" + ph, "3": p + "L" + ph,
               "8": p + "BST_" + ph, "6": P_, "7": p + "GH_" + ph, "5": p + "GL_" + ph},
              mpn="LM2105DSGR")
        d.C("1uF", rail, GND, size="0603", volt="25V", lcsc="", lcsc_ok=False)
        d.C("220nF", p + "BST_" + ph, P_, lcsc="", lcsc_ok=False)
        d.add("Q", FET, "CSD18543Q3A", FET_FP, {"5": "VBAT", "1": P_, "2": P_, "3": P_, "4": p + "GH_" + ph},
              mpn="CSD18543Q3A", note="high side")
        d.add("Q", FET, "CSD18543Q3A", FET_FP, {"5": P_, "1": GND, "2": GND, "3": GND, "4": p + "GL_" + ph},
              mpn="CSD18543Q3A", note="low side")
        d.add("TP", "Connector:TestPoint", "M%d%s" % (n, ph), "TestPoint:TestPoint_Pad_2.5x2.5mm", {"1": P_})
        # back-EMF divider, and the virtual neutral formed from the three divided signals:
        # BEMF_k - NEUTRAL = (PH_k - mean(PH)) / 11.8  (18k / 2k / 10k), ~2.1 V at 25.2 V
        d.R("18k", P_, p + "BEMF_" + ph); d.R("2k", p + "BEMF_" + ph, GND)
        d.R("10k", p + "BEMF_" + ph, p + "NEUTRAL")
    d.C("10uF", "VBAT", GND, size="1206", volt="50V", lcsc="", lcsc_ok=False)
    d.C("100nF", "VBAT", GND, size="0603", volt="50V", lcsc="", lcsc_ok=False)

d.group("Mechanical")
for _ in range(4):
    d.add("H", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", {})
DESIGN = d
