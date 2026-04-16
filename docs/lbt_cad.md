# LBT and CAD

## Overview

This document describes the current **Listen Before Talk (LBT)** and **Channel Activity Detection (CAD)** behavior in the WM1303 system.

## Core rule

**CAD is only active when LBT is enabled for the same channel.**

This dependency is enforced to keep behavior predictable in runtime, API, and UI.

## Per-channel behavior

LBT and CAD are configured **per channel**. In the current 5-channel model, this includes the user-visible channel set and any SX1261/Channel E-related logic where exposed.

## Current TX hold behavior

Older documentation often implied additional TX holding around noise-floor work. That is no longer the correct model.

### Current reality

- the separate **noise-floor hold was removed**
- the remaining deliberate TX hold is the **2-second batch window**
- routine noise-floor monitoring **does not pause TX queues**

## How LBT is used

LBT is used to reduce transmission while the channel appears occupied.

The exact measurement path depends on the current backend/radio flow, but the operational goals remain:

- protect ongoing traffic
- minimize unnecessary TX
- keep latency low
- avoid harming RX availability

## How CAD is used

CAD is used as an additional activity check where configured. Its behavior and metrics are tracked per channel and exposed to the UI/API.

## SX1261 and SPI impact

The architecture benefits from the separate SX1261 SPI path.

This matters because:

- scan/CAD/LBT support activity can be performed without overloading the main concentrator path
- RX availability is better protected
- added TX latency stays limited in normal operation

## UI behavior

The UI should reflect the dependency clearly:

- if **LBT is disabled**, CAD controls are disabled/greyed out
- enabling LBT allows CAD configuration for that channel

## Related documents

- [`radio.md`](./radio.md)
- [`tx_queue.md`](./tx_queue.md)
- [`ui.md`](./ui.md)
- [`configuration.md`](./configuration.md)
