# Teammate & Agent Handoff Log

All agents and contributors must append entries here chronologically upon finishing tasks or handoffs.

---

## [2026-11-24 00:25 IST] — Scaffolding & Agent Framework Setup
- **Author:** `@coordinator-agent`
- **Actions Completed:**
  - Initialized clean monorepo architecture (`transmitter_sim`, `receiver_demod`, `benchmarks`, `shared`, `docs`, `.agents`).
  - Created `.gitignore` ignoring temporary image dumps, compiled binaries, and python caches.
  - Added shared packet and camera contract in `shared/protocol.json`.
  - Added agent role definition cards in `.agents/` and established collaboration rules in `AGENTS.md`.
  - Initialized master tracking documents: `PROJECT_STATUS.md`, `TASKS.md`, `ARCHITECTURE.md`, `HANDOFF_LOG.md`.
  - Created boilerplate dependencies (`requirements.txt`, `receiver_demod/CMakeLists.txt`).
  - Enforced zero application code constraint.
- **Verification:**
  - Verified folder structure via terminal command.
  - Confirmed no Python or C++ application logic has been written yet.
- **Next Steps for Next Agent:**
  - `@sim-agent`: Pick up `transmitter_sim/packet_encoder.py` and implement CRC-4 and packet framing according to `ARCHITECTURE.md`.
  - `@cv-demod-agent`: Prepare Stage 1 RoI extraction harness conforming to `shared/protocol.json`.

## [2026-11-24 00:40 IST] — Repository Audit & Quality Fixes
- **Author:** `@coordinator-agent`
- **Actions Completed:**
  - **CRITICAL FIX:** Corrected packet bit-order contradiction in `ARCHITECTURE.md` Section 1 diagram (was `[Node ID] + [Preamble]`, fixed to `[Preamble] + [Node ID]` to match Section 2 protocol table).
  - Added `__init__.py` to `transmitter_sim/`, `receiver_demod/`, `benchmarks/` for Python package imports.
  - Added `.gitkeep` to empty untracked dirs: `transmitter_sim/`, `docs/math/`, `docs/presentation/`, `shared/schemas/`.
  - Enhanced `shared/protocol.json`: added `bit_offset` fields, `initial_remainder`/`final_xor` for CRC, `led_specs` section with physical parameters, `pinhole_model` camera defaults.
  - Added `scikit-image` and `Pillow` to `requirements.txt`.
  - Improved `.gitignore`: added `*.log`, `*.npy`, `*.npz`, docs build artifacts.
  - Rewrote `README.md`: added architecture highlights table, full directory tree, C++ build instructions, key features section.
  - Added two new tasks to `TASKS.md`: Test Infrastructure Setup (P1) and Protocol Schema Validation (P2).
- **Verification:**
  - Verified CRC-4-ITU polynomial (`0x13`) is correct.
  - Verified stripe width formula: `T_b/t_row = 100µs/29.6µs = 3.38 px` matches `min_stripe_height_px`.
  - Verified all pinhole projection equations are mathematically sound.
  - Confirmed no application logic was added (scaffolding-only constraint upheld).
- **Next Steps for Next Agent:**
  - `@sim-agent`: Begin `transmitter_sim/packet_encoder.py` using the corrected protocol spec.
  - `@cv-demod-agent`: Reference `protocol.json` `led_specs` and `pinhole_model` for distance estimation in Stage 4.

## [2026-11-24 01:11 IST] — Part 1: Synthetic Rolling-Shutter Channel Simulator COMPLETE
- **Author:** `@sim-agent`
- **Actions Completed:**

  ### Files Created (transmitter_sim/)
  | File | Description |
  |------|-------------|
  | `transmitter_sim/packet_encoder.py` | CRC-4-ITU encoder. `build_packet(node_id)` → 20-bit binary string. `verify_packet()` for receiver validation. |
  | `transmitter_sim/channel_model.py` | `RollingShutterSimulator` class. Pinhole projection, 2D Gaussian beam, OOK row-striping, background, noise, unmodulated mode. |
  | `transmitter_sim/run_sim.py` | Interactive live OpenCV GUI with 5 trackbars + HUD telemetry + atomic IPC write. |
  | `transmitter_sim/export_dataset.py` | Batch exporter: 9 labeled ground-truth frames + `ground_truth.json` + 3-panel comparison strip. |

  ### Files Updated
  | File | Change |
  |------|--------|
  | `shared/protocol.json` | Updated to v1.1: corrected `led_modulation_freq_hz=2500`, `row_readout_time_us=25.0`, `focal_length_px=1200`, `physical_led_diameter_m=0.25`, added `ipc` section. |
  | `ARCHITECTURE.md` | Added Section 6: finalized bit layout, CRC formula, optical parameters, file IPC table, module map. |
  | `TASKS.md` | Marked all Part 1 tasks `[DONE]`. |
  | `PROJECT_STATUS.md` | Updated Part 1 component status to DONE/Verified. |

  ### Outputs Generated
  | Path | Description |
  |------|-------------|
  | `shared/sample_frames/node105_3m_clean.png` | Node 105 @ 3m, noise=5, LED=100px |
  | `shared/sample_frames/node105_10m_clean.png` | Node 105 @ 10m, noise=5, LED=30px |
  | `shared/sample_frames/node105_18m_clean.png` | Node 105 @ 18m, noise=5, LED=16.7px |
  | `shared/sample_frames/node208_3m_clean.png` | Node 208 @ 3m, noise=5, LED=100px |
  | `shared/sample_frames/node208_10m_clean.png` | Node 208 @ 10m, noise=5, LED=30px |
  | `shared/sample_frames/node208_18m_clean.png` | Node 208 @ 18m, noise=5, LED=16.7px |
  | `shared/sample_frames/node105_5m_noise30.png` | Node 105 @ 5m, sigma=30 (high noise) |
  | `shared/sample_frames/node105_5m_phase80.png` | Node 105 @ 5m, phase_shift=80px (async) |
  | `shared/sample_frames/unmodulated_headlight.png` | Headlight (no OCC stripes, valid_packet=false) |
  | `shared/sample_frames/ground_truth.json` | Full manifest with node_id, packet bits, CRC, distance, led_px, etc. |
  | `docs/assets/sim_distance_comparison.png` | 1920×410 3-panel strip for slides |

  ### Verification
  - CRC-4-ITU self-test: Nodes 0, 105, 208, 255 → ALL PASSED ✓
  - `export_dataset.py` CRC validation: ALL 8 modulated frames PASSED ✓
  - Pixel projections verified: 3m=100px, 10m=30px, 18m=16.7px ✓

- **CLI Commands for `@cv-demod-agent` and teammates:**

  ```bash
  # Navigate to repo root
  cd /path/to/FYP_Project

  # Run the interactive live simulator (requires display / X11)
  python3 transmitter_sim/run_sim.py
  # or as module:
  python3 -m transmitter_sim.run_sim

  # Regenerate the full dataset (headless, ~2 seconds)
  python3 transmitter_sim/export_dataset.py
  # or as module:
  python3 -m transmitter_sim.export_dataset

  # Run packet encoder self-test
  python3 transmitter_sim/packet_encoder.py

  # Read ground-truth manifest
  cat shared/sample_frames/ground_truth.json | python3 -m json.tool

  # Quick Python API usage example:
  python3 - <<'EOF'
  import sys; sys.path.insert(0, '.')
  from transmitter_sim.channel_model import RollingShutterSimulator
  import cv2
  sim = RollingShutterSimulator()
  frame = sim.render(node_id=105, distance_m=5.0, noise_level=10, phase_shift_px=0)
  cv2.imwrite('/tmp/test_frame.png', frame)
  print('Frame written to /tmp/test_frame.png')
  EOF
  ```

- **Key Contract Facts for `@cv-demod-agent`:**
  - Packet: `10101010` (preamble) + 8-bit node_id + CRC-4-ITU (4 bits) = 20 bits cyclic
  - Pixels per bit: **8 rows** at baseline (f_LED=2500Hz, t_row=25µs)
  - LED aperture centered at **(960, 540)** (frame centre)
  - Gaussian sigma = `led_px_diameter / 4` → Stage 3 detrending window should be ~1× stripe_width
  - `valid_packet: false` frames (unmodulated) have NO alternating rows — solid Gaussian only
  - Live IPC frame: `shared/live_stream/latest_frame.png` (atomically replaced on each render)

- **Next Steps for `@cv-demod-agent`:**
  - Build Stage 1 (`stage1_roi.py`): Otsu/adaptive threshold → contour → bounding box over `shared/sample_frames/node105_3m_clean.png`
  - Build Stage 2–4 against `ground_truth.json` to verify 100% decode on clean frames
  - Use `unmodulated_headlight.png` to test false-positive rejection (valid_packet=false)
  - Point live-demo receiver at `shared/live_stream/latest_frame.png` (refresh ~30fps)

- **Next Steps for `@benchmark-agent`:**
  - Use `export_dataset.py` as the frame source for BER sweep (call `sim.render()` in a loop across distances)
  - Presentation strip already at `docs/assets/sim_distance_comparison.png`
