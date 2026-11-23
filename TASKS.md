# Task Backlog: Phase 2 OCC Implementation (10-Day Target)

**Priority Scale:** `P0` (Blocker / Critical Path), `P1` (High), `P2` (Medium), `P3` (Nice-to-have)

---

## Part 1: Synthetic Rolling-Shutter Image Generator (`/transmitter_sim`)
*Owner: `@sim-agent`*

- [x] `[P0]` **Packet Framing Engine (`transmitter_sim/packet_encoder.py`):** `[DONE @sim-agent 2026-11-24]`
  - Implemented 8-bit Preamble (`10101010`) attachment.
  - Implemented 8-bit Node ID payload validation (`0–255`).
  - Implemented CRC-4-ITU (`x^4 + x + 1`, poly `0x13`) shift-register algorithm and parity appending.
  - Self-test: nodes 0, 105, 208, 255 all verify correctly.
- [x] `[P0]` **Rolling Shutter Channel Simulator (`transmitter_sim/channel_model.py`):** `[DONE @sim-agent 2026-11-24]`
  - Implemented `RollingShutterSimulator` class with pinhole projection, 2D Gaussian beam profile, OOK row-striping, background + clutter.
  - Implements row-by-row temporal-to-spatial mapping using `pixels_per_bit = 1/(f_led * t_row)`.
  - Gaussian spatial intensity profile with configurable sigma.
  - Distance-to-pixel projection: 3m→100px, 10m→30px, 18m→16.7px.
- [x] `[P1]` **Optical Channel & Noise Effects (integrated in `channel_model.py`):** `[DONE @sim-agent 2026-11-24]`
  - Gaussian sensor readout noise (`sigma` = `noise_level` param).
  - Urban night/tunnel background + dim tail-light & streetlamp clutter blobs.
  - `unmodulated_mode` flag for headlight false-positive testing.
  - Configurable `phase_shift_px` for async frame start simulation.
- [x] `[P1]` **Interactive Live Demo (`transmitter_sim/run_sim.py`):** `[DONE @sim-agent 2026-11-24]`
  - OpenCV trackbars: Node ID (0–255), Distance (2–20m), Noise Level, Phase Shift, Headlight Mode.
  - HUD telemetry overlay (TX ID, binary packet, distance, px/bit, mode).
  - Atomic IPC write to `shared/live_stream/latest_frame.png`.
- [x] `[P1]` **Batch Dataset Exporter (`transmitter_sim/export_dataset.py`):** `[DONE @sim-agent 2026-11-24]`
  - 9 labeled ground-truth frames in `shared/sample_frames/` with `ground_truth.json` manifest.
  - 3-panel distance comparison strip (3m|10m|18m) → `docs/assets/sim_distance_comparison.png`.
  - All CRC checks passed at export time.

---

## Part 2: Real-Time OCC Demodulator & Visual HUD (`/receiver_demod`)
*Owner: `@cv-demod-agent`*

- [ ] `[P0]` **Stage 1: RoI Extraction & Transmitter Localization (`receiver_demod/stage1_roi.py`):**
  - Convert input frame to grayscale, apply thresholding and morphological cleanup.
  - Find emitter contours and output cropped RoI bounding box `[x, y, w, h]`.
  - *Assignee:* `@cv-demod-agent` | *Status:* `TODO`
- [ ] `[P0]` **Stage 2: 2D-to-1D Waveform Extraction (`receiver_demod/stage2_waveform.py`):**
  - Cross-row horizontal pixel averaging across the extracted LED RoI.
  - Output 1D intensity profile array representing row temporal variations.
  - *Assignee:* `@cv-demod-agent` | *Status:* `TODO`
- [ ] `[P0]` **Stage 3: Baseline Correction & Adaptive Binarization (`receiver_demod/stage3_binarize.py`):**
  - Moving-average / polynomial detrending to eliminate low-frequency Gaussian envelope.
  - Dynamic thresholding / zero-crossing detection to yield clean binary square wave.
  - *Assignee:* `@cv-demod-agent` | *Status:* `TODO`
- [ ] `[P0]` **Stage 4: Stripe Width, Preamble Sync & Bit Recovery (`receiver_demod/stage4_decoder.py`):**
  - Stripe width estimation from run-length histogram.
  - Preamble cross-correlation with `10101010` to establish packet boundary.
  - Sample payload bits, extract `Node_ID`, and compute CRC-4 to verify data integrity.
  - Pinhole distance estimation calculation from observed RoI height.
  - *Assignee:* `@cv-demod-agent` | *Status:* `TODO`
- [ ] `[P1]` **4-Quadrant Debug HUD (`receiver_demod/hud_display.py`):**
  - Build composite 1920x1080 display combining: (1) Raw frame + bbox, (2) Zoomed RoI stripes, (3) Live 1D waveform & binarization graph, (4) Telemetry stats (Node ID, CRC Pass/Fail, Distance, Latency).
  - *Assignee:* `@cv-demod-agent` | *Status:* `TODO`

---

## Part 3: Automated Benchmarking & Presentation Assets (`/benchmarks` & `/docs`)
*Owner: `@benchmark-agent`*

- [ ] `[P1]` **Automated BER vs. Distance Evaluator (`benchmarks/eval_ber_vs_distance.py`):**
  - Run synthetic sweeps across distances $d \in [2\text{m}, 30\text{m}]$ in steps of 2m.
  - Compute total transmitted vs. corrupted bits to calculate Bit Error Rate (BER).
  - Export data to `benchmarks/data/ber_results.csv`.
  - *Assignee:* `@benchmark-agent` | *Status:* `TODO`
- [ ] `[P1]` **Evaluation Plot Generator (`benchmarks/plot_results.py`):**
  - Generate publication-quality Matplotlib plots: BER vs. Distance (log scale) and PRR vs. SNR.
  - Save to `benchmarks/plots/ber_curve.png`.
  - *Assignee:* `@benchmark-agent` | *Status:* `TODO`
- [ ] `[P2]` **Presentation & Documentation Deliverables (`docs/`):**
  - Compile final LaTeX/Markdown summary of optical formulas and demo screenshots.
  - *Assignee:* `@benchmark-agent` | *Status:* `TODO`

---

## Part 4: Integration & Coordinator Oversight (`/` & `/shared`)
*Owner: `@coordinator-agent`*

- [ ] `[P0]` **End-to-End Pipeline Smoke Test:**
  - Pipe generated synthetic frame into receiver demodulator and verify 100% CRC pass rate under nominal conditions.
  - *Assignee:* `@coordinator-agent` | *Status:* `TODO`
- [ ] `[P1]` **Test Infrastructure Setup:**
  - Create `conftest.py` at repo root with shared pytest fixtures (sample packets, frame generators).
  - Add unit test directories: `transmitter_sim/tests/`, `receiver_demod/tests/`, `benchmarks/tests/`.
  - *Assignee:* `@coordinator-agent` | *Status:* `TODO`
- [ ] `[P2]` **Protocol Schema Validation:**
  - Create a JSON Schema in `shared/schemas/` to formally validate `protocol.json` structure.
  - Add a validation test that both `@sim-agent` and `@cv-demod-agent` modules load and validate the same contract.
  - *Assignee:* `@coordinator-agent` | *Status:* `TODO`
