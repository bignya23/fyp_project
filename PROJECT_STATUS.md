# Project Status: Rolling Shutter OCC Localization Framework

**Milestone:** Phase 2 (Synthetic Generator + 4-Stage Demodulator & Visual HUD)  
**Status Date:** November 24, 2026  
**Current Phase:** Scaffolding & Agent Setup (Complete)

---

## 1. High-Level Summary
- Multi-agent monorepo scaffolding initialized with dedicated role contracts and boundaries.
- Complete protocol specification created: 20-bit packet layout (`Preamble[8] + Node_ID[8] + CRC[4]`) in `shared/protocol.json`.
- Mathematical foundation and 4-stage computer vision architecture documented in `ARCHITECTURE.md`.
- No application source code implemented yet, per strict constraint.

---

## 2. Component Status Table

| Component | Responsible Agent | Status | Verified? | File Paths |
| :--- | :--- | :--- | :--- | :--- |
| **Monorepo Structure** | `@coordinator-agent` | Done | Yes | Root directory structure |
| **Agent Roles & Guidelines**| `@coordinator-agent` | Done | Yes | `AGENTS.md`, `.agents/*.md` |
| **Protocol Contract** | `@coordinator-agent` | Done | Yes | `shared/protocol.json`, `ARCHITECTURE.md` |
| **Part 1: Frame Generator** | `@sim-agent` | Pending | No | `transmitter_sim/` |
| **Part 2: 4-Stage Demodulator** | `@cv-demod-agent` | Pending | No | `receiver_demod/` |
| **Part 3: 4-Quadrant HUD** | `@cv-demod-agent` | Pending | No | `receiver_demod/` |
| **Part 4: BER Benchmarks** | `@benchmark-agent` | Pending | No | `benchmarks/` |

---

## 3. Currently In Progress
- Setup and scaffolding finalized.
- **Repository audit completed** — 1 critical protocol inconsistency fixed, 5 structural gaps filled, 8 quality improvements applied.
- Ready to dispatch initial task assignments to `@sim-agent` (Generator implementation) and `@cv-demod-agent` (Demodulator skeleton).

---

## 4. Known Blockers & Technical Risks
- *Stripe Width vs. Distance Tradeoff:* As distance increases beyond ~20m, the projected LED height shrinks, reducing stripe thickness down towards 1–2 pixels, causing aliasing. Demodulator will need robust sub-pixel interpolation or moving window averaging.
- *Ambient DC Saturation:* High ambient noise or direct headlight glare could compress the dynamic range of OOK stripes. Stage 1 RoI extraction must isolate the central emitter contour accurately.
