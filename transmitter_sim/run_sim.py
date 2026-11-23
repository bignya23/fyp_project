"""
run_sim.py — Interactive Live Demo: Transmitter Channel Simulator
@sim-agent | FYP_Project/transmitter_sim/

Opens an OpenCV GUI window with live trackbars to control:
  - Node ID (0–255)
  - Distance in metres (2–20)
  - Noise Level (0–50)
  - Phase Shift in pixels (0–160)
  - Headlight / Unmodulated Mode (0=OCC, 1=Unmodulated)

Each parameter change triggers a fresh synthetic frame render.

Also writes the latest frame atomically to:
    /shared/live_stream/latest_frame.png
so the receiver HUD can read it in real time during the live presentation demo.

Usage:
    cd /path/to/FYP_Project
    python3 -m transmitter_sim.run_sim
  or directly:
    python3 transmitter_sim/run_sim.py
"""

import os
import sys
import time
import tempfile
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Ensure repo root is in sys.path for relative imports
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from transmitter_sim.channel_model import RollingShutterSimulator, FRAME_W, FRAME_H

# ---------------------------------------------------------------------------
# IPC output path
# ---------------------------------------------------------------------------
LIVE_STREAM_DIR = _REPO_ROOT / "shared" / "live_stream"
LATEST_FRAME_PATH = LIVE_STREAM_DIR / "latest_frame.png"
LIVE_STREAM_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Display scale (1920×1080 is too large for most screens)
# ---------------------------------------------------------------------------
DISPLAY_SCALE = 0.5   # render at 50% → 960×540 for the GUI window

WINDOW_NAME = "Transmitter Channel Simulator"


def _atomic_write_png(path: Path, frame: np.ndarray) -> None:
    """
    Atomically write a frame to disk using a temp file + rename to prevent
    the receiver from reading a partially written file.
    """
    tmp_path = path.with_suffix(".tmp.png")
    cv2.imwrite(str(tmp_path), frame)
    os.replace(str(tmp_path), str(path))


def _draw_telemetry(frame: np.ndarray, sim: RollingShutterSimulator,
                    node_id: int, distance_m: float, noise_level: int,
                    phase_shift_px: int, unmodulated_mode: bool) -> None:
    """
    Draw HUD telemetry text on the frame in-place (top-left corner).
    Text is rendered on a semi-transparent dark background strip for legibility.
    """
    info = sim.get_packet_info(node_id)
    led_px = sim.get_led_px_diameter(distance_m)

    lines = [
        f"TX ID     : {node_id:3d} (0x{node_id:02X})",
        f"Binary    : {info['preamble']} | {info['node_id_bits']} | {info['crc_bits']}",
        f"Distance  : {distance_m:.1f} m",
        f"LED diam  : {led_px:.1f} px",
        f"Px/Bit    : {info['pixels_per_bit']:.1f}",
        f"Noise sigma: {noise_level}",
        f"PhaseShift: {phase_shift_px} px",
        f"Mode      : {'HEADLIGHT (Unmodulated)' if unmodulated_mode else 'OCC (Modulated)'}",
    ]

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.52
    thickness = 1
    padding = 6

    # Measure text block
    text_h = int(cv2.getTextSize("Ag", font, font_scale, thickness)[0][1] * 1.6)
    block_h = text_h * len(lines) + padding * 2
    block_w = 400

    # Dark semi-transparent background strip
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (block_w, block_h), (15, 15, 15), cv2.FILLED)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Draw each line
    for i, line in enumerate(lines):
        y = padding + (i + 1) * text_h
        cv2.putText(frame, line, (padding, y), font, font_scale,
                    (200, 230, 200), thickness, cv2.LINE_AA)


def main() -> None:
    sim = RollingShutterSimulator(add_clutter=True)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    display_w = int(FRAME_W * DISPLAY_SCALE)
    display_h = int(FRAME_H * DISPLAY_SCALE)
    cv2.resizeWindow(WINDOW_NAME, display_w, display_h)

    # --- Trackbar callbacks (OpenCV requires a callback but we poll instead) ---
    _noop = lambda v: None

    cv2.createTrackbar("Node ID",         WINDOW_NAME, 105, 255, _noop)
    cv2.createTrackbar("Distance (m)",    WINDOW_NAME, 5,   20,  _noop)
    cv2.createTrackbar("Noise Level",     WINDOW_NAME, 10,  50,  _noop)
    cv2.createTrackbar("Phase Shift (px)",WINDOW_NAME, 0,   160, _noop)
    cv2.createTrackbar("Headlight (0/1)", WINDOW_NAME, 0,   1,   _noop)

    # State cache for change detection
    prev_state = (-1, -1, -1, -1, -1)
    cached_frame: np.ndarray = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.uint8)
    fps_timer = time.time()
    fps = 0.0

    print(f"[run_sim] Window: '{WINDOW_NAME}' opened at {display_w}×{display_h}")
    print(f"[run_sim] Live IPC frame: {LATEST_FRAME_PATH}")
    print("[run_sim] Press 'q' or Esc to quit.")

    while True:
        # Read trackbar values
        node_id       = cv2.getTrackbarPos("Node ID",          WINDOW_NAME)
        distance_m    = max(2, cv2.getTrackbarPos("Distance (m)",   WINDOW_NAME))
        noise_level   = cv2.getTrackbarPos("Noise Level",      WINDOW_NAME)
        phase_shift   = cv2.getTrackbarPos("Phase Shift (px)", WINDOW_NAME)
        headlight     = cv2.getTrackbarPos("Headlight (0/1)",  WINDOW_NAME)
        unmodulated   = (headlight == 1)

        state = (node_id, distance_m, noise_level, phase_shift, headlight)
        if state != prev_state:
            # Re-render frame
            t0 = time.perf_counter()
            cached_frame = sim.render(
                node_id=node_id,
                distance_m=float(distance_m),
                noise_level=float(noise_level),
                phase_shift_px=phase_shift,
                unmodulated_mode=unmodulated,
            )
            render_ms = (time.perf_counter() - t0) * 1000
            fps = 1000.0 / max(render_ms, 1.0)
            prev_state = state

            # Atomic IPC write
            _atomic_write_png(LATEST_FRAME_PATH, cached_frame)

        # Draw telemetry overlay on a copy (don't pollute cached_frame)
        display_frame = cached_frame.copy()
        _draw_telemetry(display_frame, sim, node_id, float(distance_m),
                        noise_level, phase_shift, unmodulated)

        # FPS counter top-right
        cv2.putText(
            display_frame,
            f"Render FPS: {fps:.1f}",
            (FRAME_W - 220, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120, 200, 255), 1, cv2.LINE_AA
        )

        # Resize and show
        small = cv2.resize(display_frame, (display_w, display_h), interpolation=cv2.INTER_AREA)
        cv2.imshow(WINDOW_NAME, small)

        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), 27):  # q or Esc
            break

    cv2.destroyAllWindows()
    print("[run_sim] Exited cleanly.")


if __name__ == "__main__":
    main()
