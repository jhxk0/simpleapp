"""Flight controller: STM32F405RGT6, ICM-42688-P, BMP280, W25Q128, 3-6S input, 30.5mm mount."""
from design import Design

d = Design("fc", "Drone Flight Controller F405")
GND = "GND"

# ---------------------------------------------------------------- MCU
d.group("MCU")
mcu = {
    "VBAT": "+3V3", "VDD": "+3V3", "VSS": GND, "VDDA": "VDDA", "VSSA": GND,
    "VCAP_1": "VCAP1", "VCAP_2": "VCAP2", "NRST": "NRST", "BOOT0": "BOOT0",
    "PH0": "HSE_IN", "PH1": "HSE_OUT",
    # USB
    "PA11": "USB_DM", "PA12": "USB_DP", "PC5": "USB_DET",
    # SWD
    "PA13": "SWDIO", "PA14": "SWCLK",
    # IMU on SPI1
    "PA4": "IMU_CS", "PA5": "IMU_SCK", "PA6": "IMU_MISO", "PA7": "IMU_MOSI", "PC4": "IMU_INT1",
    # Flash on SPI3
    "PA15": "FLASH_CS", "PC10": "FLASH_SCK", "PC11": "FLASH_MISO", "PC12": "FLASH_MOSI",
    # I2C1: baro + external compass
    "PB8": "I2C_SCL", "PB9": "I2C_SDA",
    # UARTs
    "PA9": "UART1_TX", "PA10": "UART1_RX",     # receiver
    "PA2": "UART2_TX", "PA3": "UART2_RX",      # GPS
    "PB10": "UART3_TX", "PB11": "UART3_RX",    # VTX / MSP
    "PA0": "UART4_TX", "PA1": "UART4_RX",      # spare pads
    "PC6": "UART6_TX", "PC7": "UART6_RX",      # VTX SBUS / spare
    "PD2": "ESC_TLM",                          # UART5_RX
    # Motors (DShot): TIM3 CH3/CH4, TIM8 CH3/CH4
    "PB0": "M1", "PB1": "M2", "PC8": "M3", "PC9": "M4",
    # Misc
    "PA8": "LED_STRIP_MCU",    # TIM1_CH1
    "PB6": "BUZZER_MCU",       # TIM4_CH1
    "PB4": "LED_STAT1", "PB5": "LED_STAT2",
    "PC1": "CURR_ADC", "PC2": "VBAT_ADC",
    "PB2": "BOOT1",
}
d.add("U", "MCU_ST_STM32F4:STM32F405RGTx", "STM32F405RGT6", "Package_QFP:LQFP-64_10x10mm_P0.5mm",
      mcu, mpn="STM32F405RGT6", lcsc="C15742", lcsc_ok=True)
for _ in range(4):
    d.C("100nF", "+3V3", GND)
d.C("4.7uF", "+3V3", GND, size="0603")
d.add("FB", "Device:FerriteBead_Small", "600R@100MHz", "Inductor_SMD:L_0402_1005Metric",
      {"1": "+3V3", "2": "VDDA"}, mpn="BLM15AG601SN1D")
d.C("1uF", "VDDA", GND); d.C("100nF", "VDDA", GND)
d.C("2.2uF", "VCAP1", GND); d.C("2.2uF", "VCAP2", GND)
d.C("100nF", "NRST", GND)
d.R("10k", "BOOT0", GND)
d.R("10k", "BOOT1", GND)
d.add("SW", "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2",
      {"1": "+3V3", "2": "BOOT0"}, mpn="KMR211NGLFS")
d.flag("VDDA")

d.group("Clock")
d.add("Y", "Device:Crystal_GND24", "8MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
      {"1": "HSE_IN", "2": GND, "3": "HSE_OUT", "4": GND},
      mpn="X322508MSB4SI (8MHz, 20pF CL)", lcsc="C9002", note="load caps sized for CL=20pF")
d.C("33pF", "HSE_IN", GND); d.C("33pF", "HSE_OUT", GND)

# ---------------------------------------------------------------- Power
d.group("Power 5V")
# LMR33630B: 36V/3A sync buck, 1.4MHz. Vout = 1.0*(1+100k/24.9k) = 5.02V
d.add("U", "Regulator_Switching:LMR33630BDDA", "LMR33630BDDA",
      "Package_SO:Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias",
      {"1": GND, "9": GND, "2": "VBAT", "3": "BUCK_EN", "5": "BUCK_FB", "6": "BUCK_VCC",
       "7": "BUCK_BOOT", "8": "BUCK_SW"}, mpn="LMR33630BDDAR", note="PG unused")
d.C("10uF", "VBAT", GND, size="1206", volt="50V", lcsc="", lcsc_ok=False)
d.C("10uF", "VBAT", GND, size="1206", volt="50V", lcsc="", lcsc_ok=False)
d.C("100nF", "VBAT", GND, size="0603", volt="50V", lcsc="", lcsc_ok=False)
d.R("100k", "VBAT", "BUCK_EN"); d.R("27k", "BUCK_EN", GND)          # UVLO ~5.8V
d.C("100nF", "BUCK_BOOT", "BUCK_SW")
d.C("1uF", "BUCK_VCC", GND)
d.add("L", "Device:L", "4.7uH", "Inductor_SMD:L_Bourns-SRN4018",
      {"1": "BUCK_SW", "2": "+5V"}, mpn="SRN4018-4R7M (Isat 2.5A)")
d.R("100k", "+5V", "BUCK_FB"); d.R("24.9k", "BUCK_FB", GND)
d.C("22uF", "+5V", GND, size="0805", volt="10V")
d.C("22uF", "+5V", GND, size="0805", volt="10V")
d.flag("VBAT"); d.flag("+5V"); d.flag(GND)

d.group("Power 3V3")
d.add("U", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5",
      {"1": "+5V", "2": GND, "3": "+5V", "5": "+3V3"}, mpn="AP2112K-3.3TRG1", lcsc="C51118", lcsc_ok=True)
d.C("1uF", "+5V", GND); d.C("1uF", "+3V3", GND)
d.add("U", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5",
      {"1": "+5V", "2": GND, "3": "+5V", "5": "+3V3_IMU"}, mpn="AP2112K-3.3TRG1", lcsc="C51118",
      lcsc_ok=True, note="dedicated IMU supply")
d.C("1uF", "+5V", GND); d.C("1uF", "+3V3_IMU", GND)
d.add("D", "Device:LED", "RED", "LED_SMD:LED_0603_1608Metric", {"1": "LED_PWR_K", "2": "+3V3"},
      mpn="0603 red", lcsc="C2286", lcsc_ok=True)
d.R("1.5k", "LED_PWR_K", GND)

d.group("Sensing")
d.R("10k", "VBAT", "VBAT_ADC"); d.R("1k", "VBAT_ADC", GND)       # x11 divider, 36V full scale
d.C("100nF", "VBAT_ADC", GND)
d.R("1k", "CURR", "CURR_ADC"); d.C("100nF", "CURR_ADC", GND)
d.R("10k", "VBUS", "USB_DET"); d.R("20k", "USB_DET", GND)

# ---------------------------------------------------------------- USB
d.group("USB")
d.add("J", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C",
      "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
      {"A1": GND, "B1": GND, "A12": GND, "B12": GND, "S1": GND,
       "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
       "A5": "CC1", "B5": "CC2", "A6": "USB_CONN_DP", "B6": "USB_CONN_DP",
       "A7": "USB_CONN_DM", "B7": "USB_CONN_DM"},
      mpn="TYPE-C-31-M-12", lcsc="C165948", lcsc_ok=True)
d.R("5.1k", "CC1", GND); d.R("5.1k", "CC2", GND)
d.add("U", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
      {"3": "USB_CONN_DP", "4": "USB_DP", "1": "USB_CONN_DM", "6": "USB_DM", "2": GND, "5": "VBUS"},
      mpn="USBLC6-2SC6", lcsc="C7519", lcsc_ok=True)
d.add("D", "Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", {"1": "+5V", "2": "VBUS"},
      mpn="B5819W", lcsc="C8598", lcsc_ok=True, note="USB powers 5V rail; blocks backfeed")

# ---------------------------------------------------------------- Sensors
d.group("IMU")
d.add("U", "drone:ICM-42688-P", "ICM-42688-P", "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
      {"1": "IMU_MISO", "4": "IMU_INT1", "5": "+3V3_IMU", "6": GND, "8": "+3V3_IMU",
       "12": "IMU_CS", "13": "IMU_SCK", "14": "IMU_MOSI"},
      mpn="ICM-42688-P", lcsc="C1850418", lcsc_ok=True, note="verify footprint pin-1 vs datasheet")
d.C("100nF", "+3V3_IMU", GND); d.C("100nF", "+3V3_IMU", GND); d.C("2.2uF", "+3V3_IMU", GND)

d.group("Baro")
d.add("U", "Sensor_Pressure:BMP280", "BMP280",
      "Package_LGA:Bosch_LGA-8_2x2.5mm_P0.65mm_ClockwisePinNumbering",
      {"1": GND, "7": GND, "2": "+3V3", "3": "I2C_SDA", "4": "I2C_SCL", "5": GND, "6": "+3V3", "8": "+3V3"},
      mpn="BMP280", lcsc="C83291", lcsc_ok=True, note="I2C addr 0x76")
d.C("100nF", "+3V3", GND)
d.R("2.2k", "+3V3", "I2C_SCL"); d.R("2.2k", "+3V3", "I2C_SDA")

d.group("Flash")
d.add("U", "Memory_Flash:W25Q128JVS", "W25Q128JVSIQ", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
      {"1": "FLASH_CS", "2": "FLASH_MISO", "3": "FLASH_WP", "4": GND, "5": "FLASH_MOSI",
       "6": "FLASH_SCK", "7": "FLASH_HOLD", "8": "+3V3"},
      mpn="W25Q128JVSIQ", lcsc="C97521", lcsc_ok=True)
d.C("100nF", "+3V3", GND)
d.R("10k", "+3V3", "FLASH_CS"); d.R("10k", "+3V3", "FLASH_WP"); d.R("10k", "+3V3", "FLASH_HOLD")

# ---------------------------------------------------------------- IO
d.group("IO")
d.add("D", "Device:LED", "BLUE", "LED_SMD:LED_0603_1608Metric", {"2": "LED_STAT1", "1": "LED1_K"},
      mpn="0603 blue", lcsc="C72041", lcsc_ok=True)
d.R("1k", "LED1_K", GND)
d.add("D", "Device:LED", "GREEN", "LED_SMD:LED_0603_1608Metric", {"2": "LED_STAT2", "1": "LED2_K"},
      mpn="0603 green", lcsc="C72043", lcsc_ok=True)
d.R("1k", "LED2_K", GND)
# buzzer: low-side N-FET, BUZ+ = 5V
d.add("Q", "Transistor_FET:AO3400A", "AO3400A", "Package_TO_SOT_SMD:SOT-23",
      {"1": "BUZ_G", "2": GND, "3": "BUZ-"}, mpn="AO3400A", lcsc="C20917", lcsc_ok=True)
d.R("100", "BUZZER_MCU", "BUZ_G"); d.R("10k", "BUZ_G", GND)
d.add("D", "Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", {"1": "+5V", "2": "BUZ-"},
      mpn="B5819W", lcsc="C8598", lcsc_ok=True, note="buzzer flyback")
d.R("33", "LED_STRIP_MCU", "LED_STRIP")

# ---------------------------------------------------------------- Connectors
d.group("Connectors")
SH = "Connector_JST:JST_SH_SM%02dB-SRSS-TB_1x%02d-1MP_P1.00mm_Horizontal"
def conn(n, nets, label, mpn):
    d.add("J", "Connector_Generic:Conn_01x%02d" % n, label, SH % (n, n),
          {str(i + 1): x for i, x in enumerate(nets)}, mpn=mpn)
conn(8, ["VBAT", GND, "CURR", "ESC_TLM", "M1", "M2", "M3", "M4"], "ESC", "SM08B-SRSS-TB")
conn(4, ["+5V", GND, "UART1_TX", "UART1_RX"], "RX", "SM04B-SRSS-TB")
conn(6, ["+5V", GND, "UART2_TX", "UART2_RX", "I2C_SCL", "I2C_SDA"], "GPS", "SM06B-SRSS-TB")
conn(6, ["VBAT", GND, "UART3_TX", "UART3_RX", GND, "UART6_RX"], "VTX", "SM06B-SRSS-TB")

d.group("Pads")
PAD = "TestPoint:TestPoint_Pad_1.5x1.5mm"
SWD = "TestPoint:TestPoint_Pad_1.0x1.0mm"
for net, fp in [("UART4_TX", PAD), ("UART4_RX", PAD), ("UART6_TX", PAD), ("LED_STRIP", PAD),
                ("+5V", PAD), (GND, PAD), ("BUZ-", PAD), ("+5V", PAD),
                ("SWDIO", SWD), ("SWCLK", SWD), ("NRST", SWD), ("+3V3", SWD), (GND, SWD)]:
    d.add("TP", "Connector:TestPoint", net, fp, {"1": net})

DESIGN = d

d.group("Mechanical")
for _ in range(4):
    d.add("H", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", {})
DESIGN = d
