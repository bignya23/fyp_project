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

## 🚀 Quickstart & Setup

### 1. Install Python Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. (Optional) Build C++ Acceleration Module
```bash
cd receiver_demod
mkdir build && cd build
cmake ..
make
```

### 3. Multi-Agent Development Workflow
Before starting any coding task, read:
1. [AGENTS.md](AGENTS.md) for collaboration and safety rules.
2. [ARCHITECTURE.md](ARCHITECTURE.md) for the exact packet and math specification.
3. [TASKS.md](TASKS.md) to claim an unassigned task.
4. Record completed changes in [HANDOFF_LOG.md](HANDOFF_LOG.md).

---

## 🏗 Architecture Highlights

| Parameter | Value |
|-----------|-------|
| Frame Resolution | 1920 × 1080 |
| Rolling Shutter Row Readout | 29.6 µs |
| OOK Modulation Frequency | 10 kHz |
| Stripe Height | ~3.38 px per bit |
| Packet Size | 20 bits |
| CRC Polynomial | CRC-4-ITU (`x⁴ + x + 1`) |

See [ARCHITECTURE.md](ARCHITECTURE.md) for complete mathematical derivations.
