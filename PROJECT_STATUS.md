# Project Status: Rolling Shutter OCC Localization Framework

**Milestone:** Phase 2 (Synthetic Generator + 4-Stage Demodulator & Visual HUD)  
**Status Date:** November 24, 2026  
**Current Phase:** Part 1 & Part 2 Complete — Ready for `@benchmark-agent` (Part 3 BER Sweeps)

---

## 1. High-Level Summary
- Multi-agent monorepo scaffolding initialized with dedicated role contracts and boundaries.
- Complete protocol specification created: 20-bit packet layout (`Preamble[8] + Node_ID[8] + CRC[4]`) in `shared/protocol.json`.
- Mathematical foundation and 4-stage computer vision architecture documented in `ARCHITECTURE.md`.
- Part 1 (Synthetic Rolling Shutter Channel Simulator) complete and verified by `@sim-agent`.
- Part 2 (4-Stage Demodulator Engine & 4-Quadrant Visual HUD) complete and verified by `@cv-demod-agent` with 100% accuracy on sample frames and ~260 FPS throughput.

---

## 2. Component Status Table

| Component | Responsible Agent | Status | Verified? | File Paths |
| :--- | :--- | :--- | :--- | :--- |
| **Monorepo Structure** | `@coordinator-agent` | Done | Yes | Root directory structure |
| **Agent Roles & Guidelines**| `@coordinator-agent` | Done | Yes | `AGENTS.md`, `.agents/*.md` |
| **Protocol Contract** | `@coordinator-agent` | Done | Yes | `shared/protocol.json`, `ARCHITECTURE.md` |
| **Part 1: Frame Generator** | `@sim-agent` | **DONE** | **Yes** | `transmitter_sim/channel_model.py`, `transmitter_sim/packet_encoder.py`, `transmitter_sim/run_sim.py`, `transmitter_sim/export_dataset.py` |
| **Part 2: 4-Stage Demodulator** | `@cv-demod-agent` | **DONE** | **Yes** (100%) | `receiver_demod/stage1_roi.py`, `receiver_demod/stage2_waveform.py`, `receiver_demod/stage3_binarize.py`, `receiver_demod/stage4_decoder.py`, `receiver_demod/demodulator.py` |
| **Part 3: 4-Quadrant HUD** | `@cv-demod-agent` | **DONE** | **Yes** | `receiver_demod/hud_display.py`, `receiver_demod/run_receiver.py`, `receiver_demod/batch_eval.py` |
| **Part 4: BER Benchmarks** | `@benchmark-agent` | Pending | No | `benchmarks/` |

---

## 3. Currently In Progress
- Setup, Part 1 transmitter simulation, and Part 2 receiver demodulator are finalized.
- Verified 100% classification accuracy across all 9 ground-truth sample frames (including 100% false-positive rejection of unmodulated headlight).
- Measured receiver latency: mean 3.8 ms (min 1.5 ms, max 14.7 ms) equivalent to >260 FPS processing speed.
- Ready to dispatch Part 3 task assignments to `@benchmark-agent` for large-scale BER vs. distance sweeps and PRR vs. SNR evaluation.

---

## 4. Known Blockers & Technical Risks
- *Stripe Width vs. Distance Tradeoff:* As distance increases beyond ~20m, the projected LED height shrinks, reducing stripe thickness down towards 1–2 pixels, causing aliasing. Demodulator will need robust sub-pixel interpolation or moving window averaging.
- *Ambient DC Saturation:* High ambient noise or direct headlight glare could compress the dynamic range of OOK stripes. Stage 1 RoI extraction must isolate the central emitter contour accurately.
