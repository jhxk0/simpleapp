# Drone stack: F405 flight controller + 4-in-1 AM32 ESC

Two KiCad 9 boards for a 5" quad, 30.5 x 30.5 mm M3 mounting.

| Board | Size | Layers | Key parts |
|---|---|---|---|
| `fc/`  flight controller | 36 x 36 mm | 4 (1 oz) | STM32F405RGT6, ICM-42688-P, BMP280, W25Q128 16 MB, LMR33630 5 V/3 A buck, USB-C |
| `esc/` 4-in-1 ESC | 44 x 44 mm | — | 4x STM32G071K8U6N (AM32), 12x LM2105, 24x CSD18543Q3A 60 V, INA198 current sense |

**Status:** the FC is complete: ERC clean, DRC clean with schematic parity, and fab files generated.
The ESC **schematic** is complete and ERC clean, but its **layout is not finished and must not be ordered**.
See "ESC layout status" below.

Input: 3-6S LiPo. Both boards are generated from Python sources in `tools/`. Edit `tools/*_design.py`
(circuit) or `tools/*_layout.py` (placement), then rebuild; don't hand-edit the generated files unless
you're taking over in the KiCad GUI from here (which is fine — they are normal KiCad 9 projects).

## Files

```
fc/fc.kicad_pro, .kicad_sch, .kicad_pcb     KiCad 9 project (open in KiCad 9+)
fc/fc-schematic.pdf                         schematic
fc/fab/fc-gerbers.zip                       Gerbers + drill -> upload to the PCB fab
fc/fab/fc-BOM-jlcpcb.csv, fc-CPL-jlcpcb.csv JLCPCB assembly files
fc/fab/fc-BOM-full.csv                      BOM with MPNs and sourcing status
fc/drc.json, fc/erc.json                    last DRC / ERC reports
esc/esc.kicad_sch, esc-schematic.pdf        ESC schematic (complete); esc.kicad_pcb is a WIP placement only
tools/                                      generators (see "Rebuilding")
```

## FC <-> ESC link (8-pin JST-SH 1.0 mm, same pinout on both boards)

| Pin | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Signal | VBAT | GND | CURR | TLM | M1 | M2 | M3 | M4 |

Use a straight-through cable (pin 1 to pin 1). This is *not* guaranteed to match third-party ESCs —
check before plugging the FC into anything else. CURR scale: 50 mV/A (0.5 mOhm shunt x INA198 gain 100,
full scale ~66 A). TLM is not driven by this ESC; use bidirectional DShot for RPM telemetry.
The SH contacts are rated ~1 A: power a high-draw VTX from the battery pads, not through the FC.

## Flight controller pinout (STM32F405RGT6) — for your firmware

| Function | Pins | Peripheral |
|---|---|---|
| IMU ICM-42688-P | PA5 SCK, PA6 MISO, PA7 MOSI, PA4 CS, PC4 INT1 | SPI1 |
| Flash W25Q128 (blackbox) | PC10 SCK, PC11 MISO, PC12 MOSI, PA15 CS | SPI3 |
| Baro BMP280 (addr 0x76) + GPS compass | PB8 SCL, PB9 SDA (2.2k pull-ups) | I2C1 |
| Motors M1-M4 (DShot) | PB0, PB1, PC8, PC9 | TIM3 CH3/CH4, TIM8 CH3/CH4 |
| Receiver (JST "RX") | PA9 TX, PA10 RX | USART1 |
| GPS (JST "GPS") | PA2 TX, PA3 RX | USART2 |
| VTX / MSP (JST "VTX") | PB10 TX, PB11 RX; PC7 = SBUS-in pin 6 | USART3, USART6 RX |
| Spare pads TX4/RX4, TX6 | PA0, PA1, PC6 | UART4, USART6 TX |
| ESC telemetry | PD2 | UART5 RX (RX only — PC12 is used by SPI3) |
| LED strip | PA8 (33 R series) | TIM1 CH1 |
| Buzzer (low-side FET, BZ+ = 5 V) | PB6 | TIM4 CH1 |
| Status LEDs (active high) | PB4 blue, PB5 green | |
| VBAT sense | PC2, divider 10k/1k (x11) | ADC |
| Current sense from ESC | PC1 (1k + 100 nF) | ADC |
| USB detect | PC5, divider 10k/20k from VBUS | |
| USB FS | PA11 D-, PA12 D+ | OTG_FS (no VBUS sensing on PA9) |
| HSE | 8 MHz crystal | |
| Boot | BOOT button -> BOOT0 (DFU over USB) ; SWD pads DIO/CLK/RST/3V3/GND on the bottom | |

Power: VBAT -> LMR33630 buck -> +5 V (also fed from USB through a Schottky) -> two AP2112K-3.3
LDOs (one for MCU/peripherals, one dedicated to the IMU).

## ESC firmware

Each channel is pin-for-pin compatible with AM32 target **JUPITER_80_G071**
(`HARDWARE_GROUP_G0_L`, current ADC PA4, voltage ADC PA5, `TARGET_VOLTAGE_DIVIDER 285`), checked
against `Inc/targets.h` and `Mcu/g071/Src/comparator.c` in the AM32 repository:

| Function | G071 pin |
|---|---|
| Phase A/B/C high | PA10 / PA9 / PA8 (TIM1 CH3/CH2/CH1) |
| Phase A/B/C low | PB15 / PB0 / PA7 (TIM1 CH3N/CH2N/CH1N) |
| Signal in (DShot) | PC6 (TIM3 CH1) |
| BEMF A / B / C | PA0 (COMP1 INM) / PA2 (COMP2 INM) / PB7 (COMP2 INM) |
| Virtual neutral | PA1 (COMP1 INP) and PA3 (COMP2 INP) |
| Voltage sense | PA5, 27.4k/1k (x28.4) |

The driver (LM2105) has non-inverting high and low inputs, matching AM32's default (no `USE_INVERTED_LOW`).
Flash the AM32 bootloader to each MCU once through its SWD pads (DIO*n*, CLK*n*, 3V3_*n*, GND on the
bottom), then use the normal AM32 configurator through the FC passthrough. Set dead time and motor
parameters in the configurator; the target's `MILLIVOLT_PER_AMP` is irrelevant because per-ESC current
is not sensed (PA4 is tied low).

Rating: CSD18543Q3A is 60 V / 8.1 mOhm. Treat the board as **~30 A burst / ~20 A continuous per motor
with airflow**. Fine for typical 5" builds; not for high-kV 6S racing setups.

## ESC layout status (why it is paused)

A placement exists (power stage on all four edges, MCUs in the corners, battery pads in the centre).
The current path, though, cannot carry a 4-in-1's current: battery current would reach the edge
FETs through ~15 vias and 1 oz inner copper (roughly 25-30 A), against 100 A+ bursts with four motors
at full throttle. Commercial 4-in-1s put the battery pads on an edge next to the FETs and spread VBAT/GND
over several thick-copper layers (typically 6-8 layers, 2 oz). Finishing the routing on the current
architecture would produce a board that passes DRC and then overheats in flight. Options:

1. Redo the ESC layout as 6-layer, 2 oz, with edge battery pads (keeps this schematic as-is).
2. Fly the FC with an off-the-shelf 30.5 mm 4-in-1 ESC. Check its 8-pin pinout against the table
   below and re-pin the cable if it differs.

## Before you order — verification checklist

These could not be checked from inside the design environment (no access to datasheet sites or the
JLCPCB/LCSC catalogue). Each is a short check:

1. **ICM-42688-P footprint and reserved pins.** The design uses KiCad's generic
   `LGA-14_3x2.5mm_P0.5mm` footprint and leaves RESV pins 2, 3, 7, 10, 11 unconnected. Compare pin 1
   location, pad sizes and the RESV recommendations against the TDK datasheet.
2. **LCSC part numbers.** `*-BOM-full.csv` marks every line as *recalled* (from memory, likely right),
   *unverified* or *MISSING*. JLCPCB's BOM upload shows the actual match; pick equivalents for the
   missing lines (mostly 50 V caps, the shunt, ESC silicon).
3. **Assembly rotations.** JLCPCB's parts library sometimes uses a different zero-rotation than KiCad
   (QFN, SOT-23, connectors). Check the placement preview at order time and rotate as needed.
4. **(ESC) Gate-drive LDO margin.** L78L10 is rated 30 V input; 6S is 25.2 V. The 22 R + 1 uF filter helps,
   but a **low-ESR electrolytic (35 V, 470–1000 uF) across the battery pads is mandatory**.
6. **First power-up.** Use a current-limited supply (or smoke stopper), no props, one board at a time.

## Ordering (JLCPCB)

- FC: 4 layers, 1.6 mm, 1 oz, upload `fc/fab/fc-gerbers.zip`; assembly on **both sides** with the BOM and CPL.
- Minimums used: 0.1 mm track, 0.127 mm space, 0.3/0.5 mm vias — within JLCPCB's standard 4-layer capability.
- Stack-up: In1 = solid GND reference plane; In2 = signals + GND fill. Pick JLC's standard 4-layer stack-up.

## Rebuilding

Requires KiCad 9 (`kicad-cli` + `pcbnew` Python), Java 25 and Freerouting 2.4.1.

```
python3 tools/build_sch.py fc        # schematic + ERC + netlist cross-check
tools/run_route.sh fc                # place, fanout, route (Freerouting x2), pours, DRC
python3 tools/fab.py fc              # Gerbers, drill, BOM, CPL, renders
```
