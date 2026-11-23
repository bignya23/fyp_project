# Rolling Shutter Optical Camera Communication (OCC) Framework
### Offline V2I Vehicular Localization in Smart City Infrastructure
**B.Tech Final Year Project — Phase 2 Deliverable**

---

## 📌 Overview
This repository hosts the simulation, demodulation, and benchmarking pipeline for a Rolling Shutter Optical Camera Communication (OCC) system designed for GPS-denied environments (tunnels, urban canyons). Modulated streetlights encode an infrastructure Node ID via high-frequency OOK flashing, which a vehicular rolling-shutter CMOS camera records as spatial horizontal stripes. An onboard computer vision pipeline demodulates the signal to determine identity and position without external network connectivity.

### Key Features
- **20-bit packet**: `[8-bit Preamble] + [8-bit Node ID] + [4-bit CRC-4]`
- **4-stage demodulation**: RoI → Waveform → Binarization → Bit Recovery
- **4-quadrant visual HUD**: Real-time debug display with telemetry
- **Multi-agent development**: Strict domain ownership with boundary enforcement

---

## 📂 Repository Layout

```
.
├── .agents/                    # Multi-agent role charters and boundary definitions
│   ├── sim-agent.md
│   ├── cv-demod-agent.md
│   ├── benchmark-agent.md
│   └── coordinator-agent.md
├── AGENTS.md                   # Collaboration guidelines & cross-module boundaries
├── ARCHITECTURE.md             # Optical physics, packet protocol & 4-stage pipeline math
├── PROJECT_STATUS.md           # Living status table, blockers & verification metrics
├── TASKS.md                    # Granular prioritized task backlog (P0-P3)
├── HANDOFF_LOG.md              # Chronological handoff history between agents
├── requirements.txt            # Core Python environment dependencies
├── .gitignore                  # Git ignore rules for builds, dumps and cache
├── transmitter_sim/            # Part 1: Synthetic frame generator & optical noise models
│   └── __init__.py
├── receiver_demod/             # Part 2: 4-stage OpenCV demodulator & visual HUD
│   ├── __init__.py
│   └── CMakeLists.txt          # C++ build skeleton for optional native acceleration
├── benchmarks/                 # Part 3: Automated BER vs. distance evaluation scripts
│   ├── __init__.py
│   ├── data/                   # Output CSV test logs
│   └── plots/                  # Generated presentation figures
├── shared/                     # Shared packet schemas and reference frame captures
│   ├── protocol.json           # Formal JSON contract for packet structure
│   ├── schemas/                # JSON validation schemas
│   └── samples/                # Sample frames for demodulator validation
└── docs/                       # Architecture diagrams and presentation slides
    ├── math/                   # Mathematical proofs and derivations
    └── presentation/           # Presentation slides and figures
```

---

## 🚀 Quickstart & Demo Commands

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Command 1: The Live Split-Screen Demo
Open two terminal windows to run the interactive real-time IPC demonstration:

```bash
# Terminal 1 — Start the Interactive Transmitter Simulator:
python3 transmitter_sim/run_sim.py
```
*(Provides 5 interactive OpenCV trackbars: Node ID [0–255], Distance [2m–20m], Noise Level, Phase Shift, and Headlight Mode, streaming atomic frames to `shared/live_stream/latest_frame.png`)*

```bash
# Terminal 2 — Start the Real-Time 4-Quadrant Visual Demodulator HUD:
python3 receiver_demod/run_receiver.py --mode live
```
*(Watches the IPC stream with atomic read retry and renders the 4-quadrant dashboard: (1) Camera feed + color-coded RoI bbox + FPS, (2) Zoomed RoI stripes + scanlines, (3) Live 1D waveform & binarization graph, (4) Telemetry stats)*

---

### 3. Command 2: Sample Verification & Benchmark Suite
Run the automated verification tests and generate publication-quality figures:

```bash
# Step A: Verify all 9 sample frames (100% accuracy, 100% headlight rejection)
python3 receiver_demod/batch_eval.py --no-fig

# Step B: Run the full automated benchmarking suite (Sweeps A, B, C)
python3 benchmarks/run_benchmarks.py

# Step C: Generate 300 DPI publication plots and markdown summary table
python3 benchmarks/plot_results.py
```

Generated outputs will be saved to:
- `docs/assets/ber_prr_vs_distance.png` (300 DPI, PRR & BER vs. Distance curves)
- `docs/assets/detrending_ablation_snr.png` (300 DPI, With vs. Without Detrending ablation)
- `docs/assets/summary_metrics.md` (Slide presentation markdown summary table)
- `benchmarks/data/ber_results.csv` (Raw CSV metrics)
- `benchmarks/results.json` (Structured JSON benchmark output)

---

### 4. (Optional) Single Image Inspection Mode
```bash
python3 receiver_demod/run_receiver.py --mode image --path shared/sample_frames/node105_3m_clean.png
python3 receiver_demod/run_receiver.py --mode image --path shared/sample_frames/unmodulated_headlight.png
```

---

## 🏗 Architecture & Protocol Contract Highlights (Protocol v1.1)

| Parameter | Value | Specification & Derivation |
|:---|:---|:---|
| **Frame Resolution** | 1920 × 1080 px | Full HD BGR rolling-shutter CMOS sensor |
| **Row Readout Time ($t_{\text{row}}$)** | 25.0 µs | Sensor row exposure integration period |
| **LED Modulation Frequency ($f_{\text{LED}}$)** | 2500 Hz | High-frequency OOK (imperceptible to human eye) |
| **Symbol Period ($T_b$)** | 400.0 µs | $1 / f_{\text{LED}}$ nominal bit period |
| **Nominal Stripe Height ($W_{\text{bit}}$)** | 16.0 rows / bit | $W = 1 / (f_{\text{LED}} \cdot t_{\text{row}}) = 1 / (2500 \cdot 25\mu\text{s}) = 16$ px |
| **Packet Structure** | 20 bits | `Preamble [8b]` + `Node ID [8b]` + `CRC-4 [4b]` |
| **Preamble Pattern** | `10101010` (0xAA) | Alternating synchronization square wave |
| **CRC Polynomial** | CRC-4-ITU (`0x13`) | $x^4 + x + 1$ over $[Preamble + Node ID]$ |
| **Focal Length ($f$)** | 1200 px | Pinhole optical projection model |
| **Physical LED Diameter ($D$)** | 0.25 m (25 cm) | Standard luminaire aperture |
| **Distance-to-Aperture Scaling** | $P_{\text{px}} = \frac{D \cdot f}{d}$ | 3m → 100px, 8m → 37.5px, 10m → 30px, 18m → 16.7px |

See [ARCHITECTURE.md](ARCHITECTURE.md) and [shared/protocol.json](shared/protocol.json) for complete mathematical proofs.
