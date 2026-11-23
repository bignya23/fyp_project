"""
export_dataset.py — Batch Test & Slide Asset Exporter
@sim-agent | FYP_Project/transmitter_sim/

Generates a labeled ground-truth test dataset of synthetic frames into
/shared/sample_frames/ and exports presentation assets into /docs/assets/.

Outputs:
  shared/sample_frames/
    ├── node105_3m_clean.png
    ├── node105_10m_clean.png
    ├── node105_18m_clean.png
    ├── node208_3m_clean.png
    ├── node208_10m_clean.png
    ├── node208_18m_clean.png
    ├── node105_5m_noise30.png
    ├── node105_5m_phase80.png
    ├── unmodulated_headlight.png
    └── ground_truth.json
  docs/assets/
    └── sim_distance_comparison.png   (3-panel: 3m | 10m | 18m)

Usage:
    cd /path/to/FYP_Project
    python3 -m transmitter_sim.export_dataset
  or:
    python3 transmitter_sim/export_dataset.py
"""

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Ensure repo root is in sys.path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from transmitter_sim.channel_model import RollingShutterSimulator, FRAME_W, FRAME_H
from transmitter_sim.packet_encoder import build_packet, verify_packet

# ---------------------------------------------------------------------------
# Output directories
# ---------------------------------------------------------------------------
SAMPLE_FRAMES_DIR = _REPO_ROOT / "shared" / "sample_frames"
DOCS_ASSETS_DIR   = _REPO_ROOT / "docs" / "assets"
SAMPLE_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
DOCS_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Dataset manifest definition
# ---------------------------------------------------------------------------
# Each entry describes one frame to generate:
#   filename, node_id, distance_m, noise_level, phase_shift_px,
#   unmodulated_mode, description, valid_packet
DATASET_SPEC = [
    # --- Clean close / medium / far: Node 105 ---
    dict(filename="node105_3m_clean.png",
         node_id=105, distance_m=3.0,  noise_level=5.0,  phase_shift_px=0,
         unmodulated_mode=False, seed=42,
         description="Clean close-range frame, Node 105 @ 3m. LED ~100px diameter.",
         valid_packet=True),

    dict(filename="node105_10m_clean.png",
         node_id=105, distance_m=10.0, noise_level=5.0,  phase_shift_px=0,
         unmodulated_mode=False, seed=42,
         description="Clean medium-range frame, Node 105 @ 10m. LED ~30px diameter.",
         valid_packet=True),

    dict(filename="node105_18m_clean.png",
         node_id=105, distance_m=18.0, noise_level=5.0,  phase_shift_px=0,
         unmodulated_mode=False, seed=42,
         description="Clean far-range frame, Node 105 @ 18m. LED ~16px diameter.",
         valid_packet=True),

    # --- Clean close / medium / far: Node 208 ---
    dict(filename="node208_3m_clean.png",
         node_id=208, distance_m=3.0,  noise_level=5.0,  phase_shift_px=0,
         unmodulated_mode=False, seed=99,
         description="Clean close-range frame, Node 208 @ 3m.",
         valid_packet=True),

    dict(filename="node208_10m_clean.png",
         node_id=208, distance_m=10.0, noise_level=5.0,  phase_shift_px=0,
         unmodulated_mode=False, seed=99,
         description="Clean medium-range frame, Node 208 @ 10m.",
         valid_packet=True),

    dict(filename="node208_18m_clean.png",
         node_id=208, distance_m=18.0, noise_level=5.0,  phase_shift_px=0,
         unmodulated_mode=False, seed=99,
         description="Clean far-range frame, Node 208 @ 18m.",
         valid_packet=True),

    # --- High noise ---
    dict(filename="node105_5m_noise30.png",
         node_id=105, distance_m=5.0,  noise_level=30.0, phase_shift_px=0,
         unmodulated_mode=False, seed=7,
         description="High-noise frame, Node 105 @ 5m, sigma=30. Tests demodulator SNR robustness.",
         valid_packet=True),

    # --- Phase-shifted (async frame start) ---
    dict(filename="node105_5m_phase80.png",
         node_id=105, distance_m=5.0,  noise_level=8.0,  phase_shift_px=80,
         unmodulated_mode=False, seed=7,
         description="Phase-shifted frame, Node 105 @ 5m, phase=80px. Simulates async frame start.",
         valid_packet=True),

    # --- Unmodulated headlight (false-positive rejection test) ---
    dict(filename="unmodulated_headlight.png",
         node_id=0,   distance_m=6.0,  noise_level=8.0,  phase_shift_px=0,
         unmodulated_mode=True,  seed=7,
         description="Unmodulated headlight / streetlamp. No OCC stripes. valid_packet=False.",
         valid_packet=False),
]


def _add_label_overlay(frame: np.ndarray, text_lines: list[str]) -> np.ndarray:
    """
    Add a compact multi-line label overlay at the bottom of the frame.
    Returns a new annotated frame (does not modify original).
    """
    out = frame.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.6
    th = 1
    lh = 24
    pad = 8
    total_h = lh * len(text_lines) + pad * 2
    # Dark strip at bottom
    overlay = out.copy()
    cv2.rectangle(overlay, (0, FRAME_H - total_h), (FRAME_W, FRAME_H), (10, 10, 10), cv2.FILLED)
    cv2.addWeighted(overlay, 0.65, out, 0.35, 0, out)
    for i, line in enumerate(text_lines):
        y = FRAME_H - total_h + pad + (i + 1) * lh
        cv2.putText(out, line, (10, y), font, fs, (220, 230, 220), th, cv2.LINE_AA)
    return out


def _build_ground_truth_entry(spec: dict, sim: RollingShutterSimulator) -> dict:
    """Build the ground_truth.json entry for one frame spec."""
    pkt = build_packet(spec["node_id"]) if not spec["unmodulated_mode"] else "N/A"
    led_px = sim.get_led_px_diameter(spec["distance_m"])
    return {
        "filename": spec["filename"],
        "node_id": spec["node_id"],
        "node_id_binary": format(spec["node_id"], "08b") if not spec["unmodulated_mode"] else "N/A",
        "distance_m": spec["distance_m"],
        "led_px_diameter": round(led_px, 2),
        "noise_level_sigma": spec["noise_level"],
        "phase_shift_px": spec["phase_shift_px"],
        "unmodulated_mode": spec["unmodulated_mode"],
        "valid_packet": spec["valid_packet"],
        "packet_bits": pkt,
        "preamble": pkt[:8] if pkt != "N/A" else "N/A",
        "node_id_bits": pkt[8:16] if pkt != "N/A" else "N/A",
        "crc_bits": pkt[16:] if pkt != "N/A" else "N/A",
        "pixels_per_bit": sim.pixels_per_bit,
        "description": spec["description"],
        "seed": spec.get("seed"),
    }


def generate_dataset(verbose: bool = True) -> dict:
    """
    Generate all frames in DATASET_SPEC, save to SAMPLE_FRAMES_DIR,
    write ground_truth.json, and return the manifest dict.
    """
    sim = RollingShutterSimulator(add_clutter=True)
    manifest = {"frames": [], "protocol_version": "1.1", "generated_by": "@sim-agent"}

    total = len(DATASET_SPEC)
    for i, spec in enumerate(DATASET_SPEC):
        if verbose:
            print(f"[{i+1}/{total}] Generating: {spec['filename']} ...")

        t0 = time.perf_counter()
        frame = sim.render(
            node_id=spec["node_id"],
            distance_m=spec["distance_m"],
            noise_level=spec["noise_level"],
            phase_shift_px=spec["phase_shift_px"],
            unmodulated_mode=spec["unmodulated_mode"],
            seed=spec.get("seed"),
        )
        elapsed = (time.perf_counter() - t0) * 1000

        # Annotated frame for easy visual inspection
        label_lines = [
            f"Node: {spec['node_id']} | Dist: {spec['distance_m']}m | Noise: {spec['noise_level']} | Phase: {spec['phase_shift_px']}px",
            f"Mode: {'HEADLIGHT' if spec['unmodulated_mode'] else 'OCC'} | Valid: {spec['valid_packet']} | Render: {elapsed:.1f}ms",
        ]
        annotated = _add_label_overlay(frame, label_lines)

        out_path = SAMPLE_FRAMES_DIR / spec["filename"]
        cv2.imwrite(str(out_path), annotated)

        entry = _build_ground_truth_entry(spec, sim)
        manifest["frames"].append(entry)
        if verbose:
            led_px = sim.get_led_px_diameter(spec["distance_m"])
            print(f"  → Saved {out_path.name}  (LED={led_px:.1f}px, {elapsed:.1f}ms)")

    # Write ground_truth.json
    gt_path = SAMPLE_FRAMES_DIR / "ground_truth.json"
    with open(gt_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    if verbose:
        print(f"\n[✓] ground_truth.json written → {gt_path}")

    return manifest


def generate_distance_comparison_strip(verbose: bool = True) -> None:
    """
    Generate a 3-panel horizontal comparison strip:
        [3m clean] | [10m clean] | [18m clean]  for Node 105

    Saved to docs/assets/sim_distance_comparison.png.
    Each panel is rescaled to 640×360 (1/3 of full 1920-width).
    """
    sim = RollingShutterSimulator(add_clutter=True)

    distances = [3.0, 10.0, 18.0]
    panels = []

    PANEL_W = 640
    PANEL_H = 360
    font = cv2.FONT_HERSHEY_SIMPLEX

    for d in distances:
        frame = sim.render(node_id=105, distance_m=d, noise_level=5.0,
                           phase_shift_px=0, unmodulated_mode=False, seed=42)
        led_px = sim.get_led_px_diameter(d)

        # Downscale to panel size
        panel = cv2.resize(frame, (PANEL_W, PANEL_H), interpolation=cv2.INTER_AREA)

        # Label overlay
        label = f"Node 105 | {d:.0f}m | LED={led_px:.0f}px"
        cv2.rectangle(panel, (0, 0), (PANEL_W, 36), (10, 10, 10), cv2.FILLED)
        cv2.putText(panel, label, (8, 24), font, 0.65, (200, 240, 200), 1, cv2.LINE_AA)

        panels.append(panel)
        if verbose:
            print(f"  → Panel {d:.0f}m: LED diameter = {led_px:.1f} px")

    # Concatenate horizontally
    strip = np.concatenate(panels, axis=1)   # (360, 1920, 3)

    # Add a title bar at top
    title_bar = np.zeros((50, PANEL_W * 3, 3), dtype=np.uint8)
    title_bar[:] = (25, 25, 25)
    title = "Rolling-Shutter OCC Simulator — Distance Comparison (Node ID: 105)"
    cv2.putText(title_bar, title, (20, 33), font, 0.72, (180, 220, 255), 1, cv2.LINE_AA)
    strip = np.vstack([title_bar, strip])

    out_path = DOCS_ASSETS_DIR / "sim_distance_comparison.png"
    cv2.imwrite(str(out_path), strip)
    if verbose:
        print(f"[✓] Distance comparison strip → {out_path}")
        print(f"    Shape: {strip.shape[1]}×{strip.shape[0]} px")


def main() -> None:
    print("=" * 70)
    print(" Transmitter Sim — Batch Dataset Exporter (@sim-agent)")
    print("=" * 70)
    print(f" Output dir: {SAMPLE_FRAMES_DIR}")
    print(f" Assets dir: {DOCS_ASSETS_DIR}")
    print()

    # 1. Generate full labeled dataset
    t_start = time.perf_counter()
    manifest = generate_dataset(verbose=True)
    n = len(manifest["frames"])

    # 2. Generate 3-panel comparison strip
    print(f"\nGenerating 3-panel distance comparison strip ...")
    generate_distance_comparison_strip(verbose=True)

    total_ms = (time.perf_counter() - t_start) * 1000
    print(f"\n{'='*70}")
    print(f" ✓ Done. Generated {n} frames + comparison strip in {total_ms:.0f}ms")
    print(f" Frames  : {SAMPLE_FRAMES_DIR}")
    print(f" Manifest: {SAMPLE_FRAMES_DIR / 'ground_truth.json'}")
    print(f" Strip   : {DOCS_ASSETS_DIR / 'sim_distance_comparison.png'}")
    print(f"{'='*70}")

    # 3. Quick sanity check: verify CRC on all valid-packet entries
    print("\n--- CRC Self-Check ---")
    all_ok = True
    for entry in manifest["frames"]:
        if entry["valid_packet"]:
            bits = entry["packet_bits"]
            ok = verify_packet(bits)
            status = "✓" if ok else "✗ FAIL"
            print(f"  Node {entry['node_id']:3d} @ {entry['distance_m']:5.1f}m : {bits}  [{status}]")
            if not ok:
                all_ok = False
        else:
            print(f"  Node {entry['node_id']:3d} @ {entry['distance_m']:5.1f}m : (unmodulated — no CRC) [skip]")
    print(f"\n  CRC check result: {'ALL PASSED ✓' if all_ok else 'SOME FAILED ✗'}")


if __name__ == "__main__":
    main()
