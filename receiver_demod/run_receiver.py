"""
run_receiver.py — Real-Time OCC Demodulator Runner
@cv-demod-agent | FYP_Project/receiver_demod/

Launches the 4-Quadrant Visual HUD in two modes:

  --mode live                        : Watches shared/live_stream/latest_frame.png
                                       and processes each new frame at ~30 fps.
  --mode image --path <frame.png>    : Process a single frame and display/save result.

Usage
-----
  cd /path/to/FYP_Project
  python receiver_demod/run_receiver.py --mode live
  python receiver_demod/run_receiver.py --mode image --path shared/sample_frames/node105_3m_clean.png
  python receiver_demod/run_receiver.py --mode image --path shared/sample_frames/node105_3m_clean.png --save /tmp/hud_out.png
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Repo root on sys.path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from receiver_demod.demodulator import OCCDemodulator
from receiver_demod.hud_display import build_hud

# ---------------------------------------------------------------------------
# IPC path (from protocol.json)
# ---------------------------------------------------------------------------
LIVE_FRAME_PATH = _REPO_ROOT / "shared" / "live_stream" / "latest_frame.png"


# ---------------------------------------------------------------------------
# Atomic frame reader with retry
# ---------------------------------------------------------------------------
def _read_frame_atomic(path: Path, retries: int = 5, delay_s: float = 0.02) -> np.ndarray | None:
    """
    Read a PNG frame with retry logic to handle mid-write race conditions.
    Returns BGR uint8 array or None on failure.
    """
    for attempt in range(retries):
        try:
            frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if frame is not None and frame.size > 0:
                return frame
        except Exception:
            pass
        time.sleep(delay_s)
    return None


# ---------------------------------------------------------------------------
# FPS Tracker
# ---------------------------------------------------------------------------
class FPSCounter:
    def __init__(self, window: int = 30):
        self._times: list[float] = []
        self._window = window

    def tick(self) -> float:
        now = time.perf_counter()
        self._times.append(now)
        if len(self._times) > self._window:
            self._times.pop(0)
        if len(self._times) < 2:
            return 0.0
        return (len(self._times) - 1) / (self._times[-1] - self._times[0])


# ---------------------------------------------------------------------------
# Live mode
# ---------------------------------------------------------------------------
def run_live(demod: OCCDemodulator, hud_w: int, hud_h: int) -> None:
    fps_counter = FPSCounter()
    last_mtime  = -1.0
    window_name = "OCC Receiver — 4-Quadrant HUD  (press Q to quit)"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, hud_w, hud_h)

    print("[run_receiver] LIVE mode started.")
    print(f"[run_receiver] Watching: {LIVE_FRAME_PATH}")
    print("[run_receiver] Press Q (in the OpenCV window) to quit.\n")

    hud = np.zeros((hud_h, hud_w, 3), dtype=np.uint8)
    cv2.putText(hud, "Waiting for transmitter...", (hud_w // 2 - 150, hud_h // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.imshow(window_name, hud)

    while True:
        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break

        if not LIVE_FRAME_PATH.exists():
            time.sleep(0.05)
            continue

        try:
            mtime = os.path.getmtime(LIVE_FRAME_PATH)
        except OSError:
            time.sleep(0.03)
            continue

        if mtime <= last_mtime:
            continue

        frame = _read_frame_atomic(LIVE_FRAME_PATH)
        if frame is None:
            time.sleep(0.03)
            continue

        last_mtime = mtime
        result = demod.demodulate(frame)
        fps    = fps_counter.tick()
        hud    = build_hud(frame, result, fps=fps, hud_w=hud_w, hud_h=hud_h)

        cv2.imshow(window_name, hud)

        # Print status to terminal
        node_str = str(result.node_id) if result.node_id is not None else "N/A"
        print(
            f"[{time.strftime('%H:%M:%S')}] "
            f"Status: {result.status:<28} "
            f"Node: {node_str:<4} "
            f"CRC: {'OK' if result.crc_valid else '--':<3} "
            f"Latency: {result.latency_ms:5.1f}ms  "
            f"FPS: {fps:4.1f}",
            end="\r",
        )

    cv2.destroyAllWindows()
    print("\n[run_receiver] Exited cleanly.")


# ---------------------------------------------------------------------------
# Single-image mode
# ---------------------------------------------------------------------------
def run_image(
    demod    : OCCDemodulator,
    path     : Path,
    hud_w    : int,
    hud_h    : int,
    save_path: Path | None = None,
    headless : bool = False,
) -> None:
    frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if frame is None:
        print(f"[run_receiver] ERROR: Cannot read frame at {path}", file=sys.stderr)
        sys.exit(1)

    result = demod.demodulate(frame)
    hud    = build_hud(frame, result, fps=0.0, hud_w=hud_w, hud_h=hud_h)

    print(f"\n[run_receiver] Single-image mode: {path.name}")
    print(f"  Status        : {result.status}")
    print(f"  Node ID       : {result.node_id}")
    print(f"  Node ID (bin) : {result.node_id_bits}")
    print(f"  CRC bits (rx) : {result.crc_bits}")
    print(f"  CRC valid     : {result.crc_valid}")
    print(f"  Packet bits   : {result.packet_bits}")
    print(f"  Stripe px/bit : {result.stripe_width_px:.2f}")
    print(f"  Est. distance : {result.estimated_dist_m:.2f} m")
    print(f"  Latency       : {result.latency_ms:.2f} ms\n")

    if save_path:
        cv2.imwrite(str(save_path), hud)
        print(f"[run_receiver] HUD saved to {save_path}")

    if not headless:
        window_name = f"OCC Receiver — {path.name}  (press any key to exit)"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, hud_w, hud_h)
        cv2.imshow(window_name, hud)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCC Rolling-Shutter Demodulator — 4-Quadrant Visual HUD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["live", "image"],
        default="live",
        help="'live' watches the IPC frame path; 'image' processes a single PNG.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to input PNG (required for --mode image).",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Optional output path to save the HUD composite PNG.",
    )
    parser.add_argument(
        "--hud-width",  type=int, default=1280,
        help="HUD output width in pixels (default 1280).",
    )
    parser.add_argument(
        "--hud-height", type=int, default=720,
        help="HUD output height in pixels (default 720).",
    )
    parser.add_argument(
        "--roi-threshold", type=int, default=60,
        help="Brightness threshold for Stage 1 RoI detection (default 60).",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Skip OpenCV window display (useful for headless CI/export runs).",
    )
    args = parser.parse_args()

    demod = OCCDemodulator(roi_threshold=args.roi_threshold)

    if args.mode == "live":
        run_live(demod, hud_w=args.hud_width, hud_h=args.hud_height)
    else:
        if args.path is None:
            parser.error("--path is required for --mode image")
        path = args.path if args.path.is_absolute() else (_REPO_ROOT / args.path)
        run_image(
            demod,
            path=path,
            hud_w=args.hud_width,
            hud_h=args.hud_height,
            save_path=args.save,
            headless=args.headless,
        )


if __name__ == "__main__":
    main()
