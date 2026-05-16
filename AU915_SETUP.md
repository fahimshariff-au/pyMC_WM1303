# AU915 Setup Guide — pyMC_WM1303 Fork

This fork targets **AU915 Mid** as its single supported radio configuration for Australian deployments. This document explains what that means, why it was chosen, and how to configure it.

---

## Target Hardware

The pyMC_WM1303 fork runs on Raspberry Pi hardware fitted with a **WM1302 or WM1303 LoRa HAT** (SX1302/SX1303 baseband + SX1261 scanner, with an external PA stage). This hardware class was originally deployed at scale during the Helium mining era and is now widely available for repurposing as MeshCore repeaters. Common boards in this family include:

- **SenseCAP M1** (Raspberry Pi CM4 + WM1302 HAT inside a metal enclosure) — reference hardware for this fork
- **RAK Hotspot Miner / RAK7248** (Raspberry Pi + RAK2287/2247 module) — same radio chip family
- **MNTD Blackspot / Goldspot** (CM4 + WM1302)
- **Bobcat 300** and other Helium miners based on Pi + WM1302

All of these share the key characteristic that matters here: **the WM1302/1303 HAT includes an external PA**, which means it can transmit at the full **30 dBm EIRP** used in the Mid configuration. This is the hardware this fork was built for.

---

## The Target Configuration: AU915 Mid

This fork is configured for **AU915 Mid** only. There is no multi-region profile selection at runtime — if you need a different setting, adjust `config.yaml` manually (see below).

| Parameter       | Value          |
|-----------------|----------------|
| Frequency       | 915.075 MHz    |
| Bandwidth       | 125 kHz        |
| Spreading Factor| 9              |
| Coding Rate     | 4/5            |
| TX Power        | 20 dBm (radio) / 30 dBm EIRP (with WM1302 PA) |

In `config.yaml` the relevant channel block looks like:

```yaml
wm1303:
  channels:
    channel_a:
      frequency: 916200000     # ← update this to 915075000 for Mid
      bandwidth: 125000
      spreading_factor: 9
      coding_rate: "4/5"
      tx_power: 20
      preamble_length: 17
```

> **Note on tx_power**: The value in `config.yaml` is the radio output power in dBm. The WM1302 PA adds approximately 10 dBm of gain, bringing EIRP to ~30 dBm. Do not set `tx_power` above 20 in this config — the PA will bring you to the regulatory limit.

---

## Why AU915 Mid?

### The Band Is Not Empty

The Australian 915–928 MHz ISM band is heavily occupied. LoRaWAN AU915 places 64 uplink channels across the band starting at **915.2 MHz** and stepping every 200 kHz up to 927.8 MHz, each 125 kHz wide. Commercial IoT devices — smart meters, agricultural sensors, industrial telemetry — fill this space continuously.

The two settings historically used by Australian MeshCore communities both sit inside active LoRaWAN spectrum:

- **Wide (915.800 MHz, BW250kHz)**: Completely overlaps the LoRaWAN channel centred at 915.8 MHz and bleeds into adjacent channels on both sides. Field SDR observations confirmed smart meter and IoT traffic appearing as interference on Wide links in many locations.

- **Narrow (916.575 MHz, BW62.5kHz)**: Falls inside the lower half of the LoRaWAN channel centred at 916.6 MHz — not a guard band, active LoRaWAN spectrum.

### The Only Clean Gap: Below 915.2 MHz

Credit for identifying this goes to **Dan — VK2MR**, who worked through the AU915 LoRaWAN channel plan to find it.

LoRaWAN's first uplink channel is centred at 915.2 MHz with its lower edge at 915.1375 MHz. The ISM band begins at 915.0 MHz, leaving a **~137.5 kHz gap** below the LoRaWAN plan.

A 125 kHz MeshCore signal centred at 915.075 MHz occupies **915.0125–915.1375 MHz** — its upper edge touches but does not overlap the first LoRaWAN channel. This has been validated by SDR observation: the LoRaWAN traffic that fills the rest of the band is absent in this segment.

The gap at the top of the ISM band (just below 928 MHz) is not viable. The Optus 900 MHz downlink begins at 935 MHz, and front-end bleed-over from nearby high-power cell towers desensitises SX1262 receivers well into the upper ISM band. The bottom of the band is the only candidate.

### The Power Ceiling Explains the 3 dB Gap

The ACMA LIPD class licence imposes a 25 mW per 3 kHz power spectral density limit on digital modulation transmitters. This directly sets the power ceiling for each bandwidth:

| Bandwidth | PSD ceiling          |
|-----------|----------------------|
| 62.5 kHz  | ≈ 521 mW → **27 dBm** |
| 125 kHz   | ≈ 1,042 mW → **30 dBm** (bound by 1W EIRP cap) |
| 250 kHz   | > 1W → **30 dBm** (1W EIRP cap) |

Narrow's 62.5 kHz bandwidth means it is PSD-limited to approximately 27 dBm. Mid and Wide both reach the 1W EIRP cap at 30 dBm. That **3 dB power difference accounts for more than half of Mid's link budget advantage over Narrow**.

### Link Budget Comparison

| Setting | TX Power | Sensitivity | Link Budget |
|---------|----------|-------------|-------------|
| Narrow (SF7, 62.5kHz, CR4/8) | 27 dBm | −127 dBm | **154 dB** |
| Mid (SF9, 125kHz, CR4/5)     | 30 dBm | −129 dBm | **159 dB** |
| Wide (SF11, 250kHz, CR4/5)   | 30 dBm | −131.5 dBm | **161.5 dB** |

Mid leads Narrow by **5 dB**. Wide leads Mid by only 2.5 dB on paper — a margin that the IoT interference environment at 915.800 MHz typically closes in practice.

**Important caveat — hardware matters**: These figures assume 30 dBm-capable hardware. Many MeshCore nodes run bare SX1262 chips without an external PA, which caps output at approximately 22 dBm. At 22 dBm, the power advantage of Mid over Narrow is reduced to approximately 0 dB. **The full 5 dB advantage applies to fixed repeaters with external PAs — which is exactly what WM1302/1303 HAT devices provide.**

### Airtime: Mid Is as Fast as Narrow in Practice

Despite Mid's longer symbol time, its airtime for a 100-byte MeshCore packet is only ~4% greater than Narrow's:

| Setting | Airtime (100-byte packet) |
|---------|--------------------------|
| Narrow (SF7, BW62.5, CR4/8) | ~533 ms |
| Mid (SF9, BW125, CR4/5)     | ~554 ms |
| Wide (SF11, BW250, CR4/5)   | ~944 ms |

The reason: Narrow runs CR 4/8, adding 100% FEC overhead (doubling air time for the error correction bits), which largely cancels the advantage of its shorter symbol time. In real mesh operation, the ~21 ms per-packet difference does not manifest as noticeable latency. Wide at ~944 ms is approximately 1.7× slower than either.

### Decoding Depth: Mid Holds Links Narrow Drops

LoRa's ability to decode below the noise floor varies with spreading factor:

| Setting | Observed sub-noise decoding depth |
|---------|-----------------------------------|
| Narrow (SF7)  | ~−10 dB SNR |
| Mid (SF9)     | ~−16 dB SNR |
| Wide (SF11)   | ~−20 dB SNR |

Mid decodes approximately 6 dB deeper into the noise than Narrow. On links that are marginal or near-NLOS, this is the difference between a link holding and dropping — independent of the displayed SNR figure. Field testing showed links forming on Mid that had never worked on Narrow, even where the SNR reading looked similar.

Mid also runs CR 4/5 with headroom to increase to 4/6, 4/7, or 4/8 on a difficult path if needed. Narrow at CR 4/8 is already at maximum — there is no headroom remaining.

---

## Community Validation

The physics case for Mid was tested at scale across NSW by Zindello Industries in May 2026. **51 participants** tested across Wide and Narrow deployments from Tasmania through Victoria and into NSW:

- **78%** found the mesh ran better on Mid overall
- **74%** reported a positive experience switching from their previous setting
- **67%** of users could hear more repeaters on Mid (only 6% heard fewer)
- **47%** of repeater operators saw more neighbours (only 12% saw fewer)
- **84%** experienced a stable or improved noise floor
- **80%** felt Mid should be the default recommendation for Sydney/NSW

The Bathurst and Mudgee Wide meshes switched to Mid entirely. In Newcastle/Hunter significant portions transitioned. In Sydney, large sections of the former Wide user base moved across. 75% of participants are on Mid or intend to stay.

Wide is, for all practical purposes, done in NSW. The community data confirms what the physics predicts.

Sources: Zindello Industries — [Finding the Sweet Spot](https://zindello.com.au/finding-the-sweet-spot-meshcore-lora-settings-in-the-australian-900mhz-band/) | [Well, That Was Something](https://zindello.com.au/well-that-was-something/)

---

## Narrow / Eastmesh Coexistence

Narrow (916.575 MHz, SF7, BW62.5kHz) remains the foundation of the Eastmesh spanning Tasmania through Victoria and into NSW. It is not going away.

**Mid-to-Narrow bridges are viable and in active use.** Mid and Narrow are separated by approximately **1.5 MHz**, which is better frequency separation than the old Narrow/Wide pairing (~775 kHz). A Mid-to-Narrow bridge therefore has less desensitisation risk than bridges that previously existed. That said, bridges should be set up carefully:

- Antenna selection and physical isolation between the two radios matters
- Filtering will typically be required in a properly engineered bridge installation
- The ~2× improvement in frequency separation compared to old Narrow/Wide pairings makes this achievable with the right hardware

---

## The Optus Caveat

Approximately 10% of testers in the NSW community trial experienced a worse noise floor on Mid. The most likely cause at affected sites is proximity to dense Optus 900 MHz infrastructure.

Optus holds a 2×25 MHz FDD allocation (Band 8):
- Uplink (handsets → towers): **890–915 MHz** — immediately below Mid's 915.075 MHz operating frequency
- Downlink (towers → phones): **935–960 MHz** — above the ISM band, but front-end bleed-over from high-power tower transmitters can raise the noise floor across a wide range

Mid at 915.075 MHz sits only 75 kHz above the Optus uplink boundary. In practice, worst-case analysis (phone directly below a rooftop repeater) suggests the noise contribution is in the order of the thermal noise floor — present but not dominant. All three MeshCore settings sit within 1.6 MHz of the 915 MHz boundary, so none has a structural advantage here.

**If your repeater site shows unexpectedly poor performance on Mid**: use an SDR to take an interference profile. Strong Optus tower signals (935–960 MHz) desensitising the front end, or high uplink noise floor just below 915 MHz, will be visible. Mitigation options include additional front-end filtering, antenna repositioning, or site relocation.

---

## What This Fork Does NOT Support

This fork configures AU915 Mid only. There is no runtime region selection or profile system. If you are deploying:

- **In another country / region**: You will need to manually adjust `frequency`, `bandwidth`, `spreading_factor`, `coding_rate`, and `tx_power` in `config.yaml` to match your local band plan and regulatory limits. A multi-region profile system is a planned future improvement.
- **AU915 Narrow (Eastmesh)**: Manually set `frequency: 916575000`, `bandwidth: 62500`, `spreading_factor: 7`, `coding_rate: "4/8"`, `tx_power: 17` (≈ 27 dBm EIRP with WM1302 PA — check your hardware's PA gain).
- **EU868**: Set `frequency: 868100000`, `bandwidth: 125000`, `spreading_factor: 7`, `coding_rate: "4/5"`, `tx_power: 14` (14 dBm radio output → ≈ 20 dBm EIRP, within 25 mW ERP EU limit).

> These manual overrides are unsupported and untested on this fork. Use at your own risk and verify your local regulatory requirements.

---

## Summary

This fork is built for Pi + WM1302/WM1303 HAT hardware — whether that is a SenseCAP M1, a repurposed Helium miner, or any similar Pi-based build — running MeshCore repeater firmware in the Australian 915–928 MHz ISM band.

The configuration target is **AU915 Mid: 915.075 MHz, SF9, BW125kHz, CR4/5, 30 dBm EIRP**.

Mid occupies the only clean gap below the LoRaWAN channel plan in the Australian band. It runs at the full regulatory power ceiling (30 dBm), decodes approximately 6 dB deeper into the noise than Narrow, and has essentially the same on-air airtime. Community testing across NSW confirmed these physics predictions: 78% of 51 participants found the mesh ran better on Mid overall, and 80% felt it should be the default for Sydney/NSW.

The hardware this fork targets — Pi + WM1302/WM1303 with external PA — is exactly the hardware class where the full 30 dBm link budget advantage applies.
