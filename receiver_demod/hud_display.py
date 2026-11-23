"""
hud_display.py — 4-Quadrant Real-Time Visual HUD
@cv-demod-agent | FYP_Project/receiver_demod/

Builds a composite 1280×720 (or 1600×900) OpenCV dashboard:

  Q1 (Top-Left)    : Full camera feed + color-coded RoI bounding box + latency/FPS
  Q2 (Top-Right)   : Zoomed-in cropped RoI stripes + center scanlines overlay
  Q3 (Bottom-Left) : Live 1D waveform chart (raw + baseline, detrended + threshold + markers)
  Q4 (Bottom-Right): High-contrast Telemetry Status Panel
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from receiver_demod.demodulator import DemodResult

# ---------------------------------------------------------------------------
# HUD layout constants
# ---------------------------------------------------------------------------
HUD_W   : int = 1280
HUD_H   : int = 720
HALF_W  : int = HUD_W // 2   # 640
HALF_H  : int = HUD_H // 2   # 360

# Colour palette (BGR)
COL_GREEN   = (60,  220,  60)
COL_YELLOW  = (30,  220, 220)
COL_RED     = (50,   50, 230)
COL_WHITE   = (240, 240, 240)
COL_GREY    = (100, 100, 100)
COL_DARK    = (20,   20,  20)
COL_BLUE    = (220,  80,  30)
COL_ORANGE  = (20,  140, 255)
COL_CYAN    = (220, 200,  30)
COL_LOCKED  = (60,  220,  60)   # green
COL_REJECT  = (30,  220, 220)   # yellow
COL_NO_ROI  = (50,   50, 230)   # red

FONT       = cv2.FONT_HERSHEY_SIMPLEX
FONT_SMALL = 0.42
FONT_MED   = 0.55
FONT_LARGE = 0.75
THICK_1    = 1
THICK_2    = 2


def _status_color(status: str) -> Tuple[int, int, int]:
    if status == "LOCKED":
        return COL_LOCKED
    if status == "NO_ROI":
        return COL_NO_ROI
    return COL_REJECT


# ---------------------------------------------------------------------------
# Main builder function
# ---------------------------------------------------------------------------
def build_hud(
    frame_bgr  : np.ndarray,
    result     : DemodResult,
    fps        : float = 0.0,
    hud_w      : int   = HUD_W,
    hud_h      : int   = HUD_H,
) -> np.ndarray:
    """
    Compose the 4-quadrant HUD image.

    Parameters
    ----------
    frame_bgr : Original 1920×1080 BGR frame.
    result    : OCCDemodulator.demodulate() output.
    fps       : Live frames-per-second (displayed in Q1).
    hud_w, hud_h : Output canvas size (default 1280×720).

    Returns
    -------
    HUD image as uint8 BGR array of shape (hud_h, hud_w, 3).
    """
    hw = hud_w // 2
    hh = hud_h // 2

    canvas = np.zeros((hud_h, hud_w, 3), dtype=np.uint8)

    # Draw each quadrant
    q1 = _build_q1(frame_bgr, result, fps, hw, hh)
    q2 = _build_q2(frame_bgr, result, hw, hh)
    q3 = _build_q3(result, hw, hh)
    q4 = _build_q4(result, hw, hh)

    canvas[0   :hh,  0  :hw ] = q1
    canvas[0   :hh,  hw :hud_w] = q2
    canvas[hh  :hud_h, 0  :hw ] = q3
    canvas[hh  :hud_h, hw :hud_w] = q4

    # Dividers
    cv2.line(canvas, (hw, 0), (hw, hud_h), COL_GREY, 1)
    cv2.line(canvas, (0, hh), (hud_w, hh), COL_GREY, 1)

    return canvas


# ---------------------------------------------------------------------------
# Q1 — Full Frame + Bounding Box + Latency / FPS
# ---------------------------------------------------------------------------
def _build_q1(
    frame_bgr: np.ndarray,
    result: DemodResult,
    fps: float,
    pw: int, ph: int,
) -> np.ndarray:
    q = cv2.resize(frame_bgr, (pw, ph), interpolation=cv2.INTER_AREA)

    # Scale bounding box to thumbnail size
    if result.roi_bbox is not None:
        fh, fw = frame_bgr.shape[:2]
        x, y, w, h = result.roi_bbox
        sx = pw / fw
        sy = ph / fh
        bx  = int(x * sx)
        by  = int(y * sy)
        bw  = max(int(w * sx), 2)
        bh  = max(int(h * sy), 2)
        col = _status_color(result.status)
        cv2.rectangle(q, (bx, by), (bx + bw, by + bh), col, THICK_2)
        cv2.putText(q, result.status, (bx, max(by - 6, 10)),
                    FONT, FONT_SMALL, col, THICK_1, cv2.LINE_AA)

    # Latency & FPS overlay
    _text(q, f"Latency: {result.latency_ms:.1f} ms", (8, 18), FONT_SMALL, COL_CYAN)
    _text(q, f"FPS: {fps:.1f}", (8, 36), FONT_SMALL, COL_CYAN)
    _text(q, "Q1: Camera Feed", (8, ph - 8), FONT_SMALL, COL_GREY)

    return q


# ---------------------------------------------------------------------------
# Q2 — Zoomed Cropped RoI Stripes + Scanlines
# ---------------------------------------------------------------------------
def _build_q2(
    frame_bgr: np.ndarray,
    result: DemodResult,
    pw: int, ph: int,
) -> np.ndarray:
    panel = np.full((ph, pw, 3), COL_DARK, dtype=np.uint8)

    if result.roi_bbox is None:
        _text(panel, "No RoI detected", (10, ph // 2), FONT_MED, COL_REJECT)
        _text(panel, "Q2: Zoomed RoI", (8, ph - 8), FONT_SMALL, COL_GREY)
        return panel

    x, y, w, h = result.roi_bbox
    crop = frame_bgr[y : y + h, x : x + w]
    if crop.size == 0:
        _text(panel, "Empty crop", (10, ph // 2), FONT_MED, COL_REJECT)
        return panel

    # Zoom to fill panel (nearest-neighbor to preserve stripe fidelity)
    zoomed = cv2.resize(crop, (pw, ph), interpolation=cv2.INTER_NEAREST)

    # Overlay central scanline markers (3 horizontal lines at 25%, 50%, 75%)
    for frac in [0.25, 0.50, 0.75]:
        yl = int(frac * ph)
        cv2.line(zoomed, (0, yl), (pw, yl), COL_CYAN, 1, cv2.LINE_AA)

    # Center vertical marker
    cv2.line(zoomed, (pw // 2, 0), (pw // 2, ph), COL_CYAN, 1, cv2.LINE_AA)

    panel = zoomed
    _text(panel, f"RoI {w}x{h} px | d~{result.estimated_dist_m:.1f}m",
          (8, 16), FONT_SMALL, COL_WHITE)
    _text(panel, f"Stripe: {result.stripe_width_px:.1f} px/bit",
          (8, 32), FONT_SMALL, COL_YELLOW)
    _text(panel, "Q2: Zoomed Stripes", (8, ph - 8), FONT_SMALL, COL_GREY)

    return panel


# ---------------------------------------------------------------------------
# Q3 — Live 1D Waveform Chart
# ---------------------------------------------------------------------------
def _build_q3(result: DemodResult, pw: int, ph: int) -> np.ndarray:
    panel = np.full((ph, pw, 3), (15, 15, 15), dtype=np.uint8)

    # Axis margins
    ml, mr, mt, mb = 50, 10, 25, 50

    plot_w = pw - ml - mr
    plot_h = (ph - mt - mb) // 2   # split into two sub-plots

    if result.raw_1d_signal.size == 0:
        _text(panel, "No signal data", (ml, ph // 2), FONT_MED, COL_REJECT)
        _text(panel, "Q3: Waveform", (8, ph - 8), FONT_SMALL, COL_GREY)
        return panel

    raw   = result.raw_1d_signal
    base  = result.baseline_curve
    det   = result.detrended_signal
    thr   = result.threshold_curve

    # --- Sub-plot A : Raw + Baseline (top half) ---
    ya0 = mt
    ya1 = mt + plot_h
    _draw_axes(panel, ml, ya0, plot_w, plot_h, "Raw Intensity + Baseline", mb)
    _plot_signal(panel, raw,  ml, ya0, plot_w, plot_h, (100, 180, 255), lw=1)
    _plot_signal(panel, base, ml, ya0, plot_w, plot_h, COL_ORANGE,       lw=2)

    # Legend A
    cv2.rectangle(panel, (ml + 2, ya0 + 4), (ml + 14, ya0 + 10), (100, 180, 255), -1)
    _text(panel, "Raw",      (ml + 18, ya0 + 10), 0.35, COL_WHITE)
    cv2.rectangle(panel, (ml + 50, ya0 + 4), (ml + 62, ya0 + 10), COL_ORANGE, -1)
    _text(panel, "Baseline", (ml + 66, ya0 + 10), 0.35, COL_WHITE)

    # --- Sub-plot B : Detrended + Threshold + Binary markers (bottom half) ---
    yb0 = ya1 + mb
    yb1 = yb0 + plot_h
    _draw_axes(panel, ml, yb0, plot_w, plot_h, "Detrended + Threshold + Bits", mb)
    _plot_signal(panel, det, ml, yb0, plot_w, plot_h, (100, 220, 100), lw=1)
    _plot_signal(panel, thr, ml, yb0, plot_w, plot_h, COL_YELLOW,      lw=1)

    # Zero line in detrended sub-plot
    if det.size > 0:
        d_min, d_max = det.min(), det.max()
        d_range = d_max - d_min if d_max != d_min else 1.0
        zero_norm = (0.0 - d_min) / d_range
        zero_y = int(yb0 + (1.0 - zero_norm) * plot_h)
        cv2.line(panel, (ml, zero_y), (ml + plot_w, zero_y), COL_GREY, 1)

    # Bit sampling markers (small vertical ticks at preamble + each sampled bit)
    if result.stripe_width_px > 0 and det.size > 0:
        d_min_b, d_max_b = det.min(), det.max()
        d_range_b = d_max_b - d_min_b if d_max_b != d_min_b else 1.0
        n = det.size
        step = result.stripe_width_px
        pos = step / 2.0
        while pos < n:
            xi = ml + int((pos / n) * plot_w)
            xi = min(xi, ml + plot_w - 1)
            # value at that point
            si = min(int(pos), n - 1)
            val_norm = (det[si] - d_min_b) / d_range_b
            yi_pt = int(yb0 + (1.0 - val_norm) * plot_h)
            cv2.drawMarker(panel, (xi, yi_pt), COL_RED,
                           cv2.MARKER_TILTED_CROSS, 6, 1, cv2.LINE_AA)
            pos += step

    # Legend B
    cv2.rectangle(panel, (ml + 2,  yb0 + 4), (ml + 14, yb0 + 10), (100, 220, 100), -1)
    _text(panel, "Detrended",  (ml + 18, yb0 + 10), 0.35, COL_WHITE)
    cv2.rectangle(panel, (ml + 80, yb0 + 4), (ml + 92, yb0 + 10), COL_YELLOW, -1)
    _text(panel, "Threshold",  (ml + 96, yb0 + 10), 0.35, COL_WHITE)
    cv2.rectangle(panel, (ml + 158, yb0 + 4), (ml + 170, yb0 + 10), COL_RED, -1)
    _text(panel, "Bit sample", (ml + 174, yb0 + 10), 0.35, COL_WHITE)

    _text(panel, "Q3: Signal Pipeline", (8, ph - 8), FONT_SMALL, COL_GREY)
    return panel


# ---------------------------------------------------------------------------
# Q4 — Telemetry Status Panel
# ---------------------------------------------------------------------------
def _build_q4(result: DemodResult, pw: int, ph: int) -> np.ndarray:
    panel = np.full((ph, pw, 3), (10, 15, 20), dtype=np.uint8)
    col   = _status_color(result.status)

    # Header bar
    cv2.rectangle(panel, (0, 0), (pw, 36), col, -1)
    _text(panel, "OCC TELEMETRY", (pw // 2 - 70, 24), FONT_LARGE, COL_DARK, thick=2)

    rows = [
        ("STATUS",           result.status,                              col),
        ("PREAMBLE SYNC",    "LOCKED" if result.preamble_offset >= 0
                              else "NO SYNC",                             col),
        ("NODE ID (DEC)",    str(result.node_id)
                              if result.node_id is not None else "—",    COL_WHITE),
        ("NODE ID (HEX)",    f"0x{result.node_id:02X}"
                              if result.node_id is not None else "—",    COL_WHITE),
        ("NODE ID (BIN)",    result.node_id_bits or "—",                 COL_CYAN),
        ("CRC BITS (RX)",    result.crc_bits or "—",                     COL_CYAN),
        ("CRC CHECK",        "PASS ✓" if result.crc_valid else "FAIL ✗", COL_GREEN if result.crc_valid else COL_RED),
        ("PACKET (20b)",     result.packet_bits[:20] or "—",             COL_YELLOW),
        ("STRIPE  px/bit",   f"{result.stripe_width_px:.1f} px",         COL_WHITE),
        ("EST. DISTANCE",    f"{result.estimated_dist_m:.2f} m",         COL_WHITE),
        ("LATENCY",          f"{result.latency_ms:.2f} ms",              COL_WHITE),
    ]

    y0 = 50
    line_h = max((ph - y0 - 10) // len(rows), 20)

    for i, (label, value, vcol) in enumerate(rows):
        y = y0 + i * line_h
        if y + line_h > ph - 10:
            break
        # label
        _text(panel, f"{label:<18}", (8, y + 14), FONT_SMALL, COL_GREY)
        # separator
        cv2.line(panel, (142, y + 2), (142, y + line_h - 2), COL_GREY, 1)
        # value
        _text(panel, value, (148, y + 14), FONT_SMALL, vcol)

    _text(panel, "Q4: Telemetry", (8, ph - 8), FONT_SMALL, COL_GREY)
    return panel


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def _text(
    img: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    scale: float,
    color: Tuple[int, int, int],
    thick: int = 1,
) -> None:
    cv2.putText(img, text, pos, FONT, scale, color, thick, cv2.LINE_AA)


def _draw_axes(
    panel: np.ndarray,
    ml: int, y0: int, pw: int, ph: int,
    title: str, mb: int,
) -> None:
    """Draw a simple plot box with title."""
    x1, y1 = ml + pw, y0 + ph
    cv2.rectangle(panel, (ml, y0), (x1, y1), COL_GREY, 1)
    _text(panel, title, (ml + 2, y0 - 6), 0.35, COL_WHITE)


def _plot_signal(
    panel: np.ndarray,
    signal: np.ndarray,
    ml: int, y0: int,
    pw: int, ph: int,
    color: Tuple[int, int, int],
    lw: int = 1,
) -> None:
    """Plot a 1D signal as a line in the given bounding rectangle."""
    if signal.size < 2:
        return
    s_min = signal.min()
    s_max = signal.max()
    s_range = s_max - s_min if s_max != s_min else 1.0

    n = len(signal)
    pts = []
    for i, v in enumerate(signal):
        xi = ml + int((i / (n - 1)) * (pw - 1))
        yi = y0 + int((1.0 - (v - s_min) / s_range) * (ph - 1))
        yi = max(y0, min(y0 + ph - 1, yi))
        pts.append((xi, yi))

    pts_arr = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(panel, [pts_arr], False, color, lw, cv2.LINE_AA)
