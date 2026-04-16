# TX Queue

## Overview

The WM1303 implementation uses **per-channel TX queues** to keep transmission handling predictable while preserving RX priority as much as possible.

## Main responsibilities

TX queue logic includes:

- per-channel buffering
- TTL handling
- queue depth/overflow management
- LBT checks
- CAD-related gating where enabled
- fair scheduling behavior

## Current hold model

The current behavior should be described as follows:

- the old separate noise-floor TX hold was removed
- the remaining deliberate hold is the **2-second batch window**
- routine noise-floor monitoring does **not pause TX queues**

## Design intent

The queue system tries to balance:

- fast TX after enqueue
- minimal unnecessary delay
- RX-first system behavior
- per-channel fairness

## Related documents

- [`lbt_cad.md`](./lbt_cad.md)
- [`radio.md`](./radio.md)
- [`architecture.md`](./architecture.md)
