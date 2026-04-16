# Hardware

## Overview

The hardware platform is a **SenseCAP M1** with a **WM1303 concentrator HAT** and an **SX1261 companion radio path**.

The current project should be read as a **5-channel radio platform**, not only as a classic concentrator setup.

## Main hardware responsibilities

| Component | Responsibility |
|---|---|
| SX1302 / SX1250 path | Main concentrator RX/TX path for Channels A-D |
| SX1261 path | Channel E-related behavior plus scan/CAD/LBT support roles |
| Raspberry Pi | Host runtime, SPI/GPIO control, process supervision |

## SPI layout

| SPI device | Purpose |
|---|---|
| `/dev/spidev0.0` | Main concentrator path |
| `/dev/spidev0.1` | SX1261 path |

This split is important for performance and isolation.

## Why the SPI split matters

The separate SX1261 path helps ensure that:

- the concentrator RX path remains protected
- scan/CAD/LBT-related work can run independently
- TX latency impact stays limited
- RX priority remains the guiding principle

## About SPI speed

Earlier documentation contained uncertainty around SPI speed wording. The important current explanation is:

- the implementation uses an SPI configuration that is sufficient for the present concentrator and SX1261 workflow
- later optimization work improved throughput and burst handling where needed
- users should focus on the functional split and stability characteristics rather than assuming a single old fixed-speed story covers all current behavior

## Platform preparation

The installation flow enables the required platform interfaces such as:

- SPI
- I2C where needed by the platform setup
- required user/group permissions for radio access

## Related documents

- [`architecture.md`](./architecture.md)
- [`installation.md`](./installation.md)
- [`channel_e_sx1261.md`](./channel_e_sx1261.md)
