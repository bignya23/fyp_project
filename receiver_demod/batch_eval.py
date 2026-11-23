"""
batch_eval.py — Sample Dataset Verification & Slide Asset Generator
@cv-demod-agent | FYP_Project/receiver_demod/

Runs OCCDemodulator across all frames in shared/sample_frames/ground_truth.json,
prints a pass/fail accuracy table, and saves a 4-panel pipeline figure for
Node_105 to docs/assets/demod_pipeline_4stage.png.

Usage
-----
  cd /path/to/FYP_Project
  python receiver_demod/batch_eval.py
  python receiver_demod/batch_eval.py --verbose
  python receiver_demod/batch_eval.py --save-fig docs/assets/demod_pipeline_4stage.png
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")          # headless rendering — no display required
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ---------------------------------------------------------------------------
# Repo root on sys.path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from receiver_demod.demodulator import OCCDemodulator, DemodResult

GROUND_TRUTH_PATH = _REPO_ROOT / "shared" / "sample_frames" / "ground_truth.json"
SAMPLE_FRAMES_DIR = _REPO_ROOT / "shared" / "sample_frames"
DOCS_ASSETS_DIR   = _REPO_ROOT / "docs" / "assets"
DEFAULT_FIG_PATH  = DOCS_ASSETS_DIR / "demod_pipeline_4stage.png"

# ANSI colour codes for terminal output
_GRN = "\033[92m"
_RED = "\033[91m"
_YLW = "\033[93m"
_RST = "\033[0m"
_BLD = "\033[1m"


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------
def run_batch(
    demod   : OCCDemodulator,
    verbose : bool = False,
) -> tuple[list[dict], float]:
    """
    Demodulate every frame in ground_truth.json and collect results.

    Returns
    -------
    (results_list, accuracy_percent)
    """
    with open(GROUND_TRUTH_PATH, "r") as fh:
        gt = json.load(fh)

    frames = gt["frames"]
    results = []
    n_pass = 0
    n_total = 0

    print(f"\n{'='*80}")
    print(f"  OCC DEMODULATOR — BATCH EVALUATION   (Protocol v{gt.get('protocol_version','?')})")
    print(f"{'='*80}")
    print(
        f"  {'Frame':<35} {'Expected Node':>13} {'Decoded Node':>12} "
        f"{'CRC':>5} {'Status':<30} {'Lat ms':>7}"
    )
    print(f"  {'-'*35} {'-'*13} {'-'*12} {'-'*5} {'-'*30} {'-'*7}")

    for entry in frames:
        fname          = entry["filename"]
        expected_node  = entry["node_id"] if entry["valid_packet"] else None
        valid_packet   = entry["valid_packet"]
        frame_path     = SAMPLE_FRAMES_DIR / fname

        if not frame_path.exists():
            print(f"  {_RED}MISSING: {fname}{_RST}")
            continue

        frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if frame is None:
            print(f"  {_RED}UNREADABLE: {fname}{_RST}")
            continue

        result: DemodResult = demod.demodulate(frame)
        n_total += 1

        # Determine pass/fail
        if not valid_packet:
            # Expect rejection
            is_pass = result.node_id is None or result.status != "LOCKED"
            pass_str = f"{_GRN}PASS (rejected){_RST}" if is_pass else f"{_RED}FAIL (false pos){_RST}"
        else:
            # Expect correct node_id with CRC valid
            is_pass = (
                result.node_id == expected_node and result.crc_valid
            )
            pass_str = f"{_GRN}PASS{_RST}" if is_pass else f"{_RED}FAIL{_RST}"

        if is_pass:
            n_pass += 1

        exp_str  = str(expected_node) if expected_node is not None else "REJECT"
        dec_str  = str(result.node_id) if result.node_id is not None else "—"
        crc_str  = "OK" if result.crc_valid else "--"

        print(
            f"  {fname:<35} {exp_str:>13} {dec_str:>12} "
            f"{crc_str:>5} {pass_str:<42} {result.latency_ms:>6.1f}"
        )

        if verbose:
            print(f"    Status: {result.status}")
            print(f"    Stripe: {result.stripe_width_px:.2f} px/bit | "
                  f"RoI: {result.roi_bbox} | "
                  f"Dist: {result.estimated_dist_m:.2f}m")
            print(f"    PacketBits: {result.packet_bits}")
            print()

        results.append({
            "filename"      : fname,
            "expected_node" : expected_node,
            "decoded_node"  : result.node_id,
            "valid_packet"  : valid_packet,
            "is_pass"       : is_pass,
            "crc_valid"     : result.crc_valid,
            "status"        : result.status,
            "latency_ms"    : result.latency_ms,
            "stripe_px"     : result.stripe_width_px,
            "result"        : result,
        })

    accuracy = 100.0 * n_pass / n_total if n_total > 0 else 0.0
    print(f"\n  {'-'*80}")
    acc_col = _GRN if accuracy == 100.0 else (_YLW if accuracy >= 80 else _RED)
    print(f"  {_BLD}ACCURACY: {acc_col}{accuracy:.1f}%{_RST}{_BLD}  ({n_pass}/{n_total} frames){_RST}")
    print(f"{'='*80}\n")

    return results, accuracy


# ---------------------------------------------------------------------------
# 4-Panel pipeline figure generator
# ---------------------------------------------------------------------------
def save_pipeline_figure(
    demod       : OCCDemodulator,
    target_node : int = 105,
    fig_path    : Path = DEFAULT_FIG_PATH,
) -> None:
    """
    Generate a high-resolution 4-panel pipeline breakdown figure for
    the Node_105 @ 3m clean frame and save to fig_path.

    Panel layout:
      [P1] Original BGR frame with RoI bounding box
      [P2] Zoomed 2D RoI crop (stripe detail)
      [P3] Stage 2+3 waveforms (raw, baseline, detrended, threshold)
      [P4] Recovered binary bit-stream snippet + telemetry summary
    """
    # Find Node_105 @ 3m frame in ground truth
    with open(GROUND_TRUTH_PATH, "r") as fh:
        gt = json.load(fh)

    target_frame = None
    for entry in gt["frames"]:
        if entry.get("node_id") == target_node and entry.get("distance_m", 99) <= 5.0:
            target_frame = entry
            break

    if target_frame is None:
        # fall back to any Node 105 frame
        for entry in gt["frames"]:
            if entry.get("node_id") == target_node:
                target_frame = entry
                break

    if target_frame is None:
        print(f"[batch_eval] WARNING: No frame found for Node {target_node}. Skipping figure.", file=sys.stderr)
        return

    fname = target_frame["filename"]
    frame_path = SAMPLE_FRAMES_DIR / fname
    if not frame_path.exists():
        print(f"[batch_eval] WARNING: Frame file not found: {frame_path}", file=sys.stderr)
        return

    frame_bgr = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
    if frame_bgr is None:
        print(f"[batch_eval] WARNING: Cannot read {frame_path}", file=sys.stderr)
        return

    result: DemodResult = demod.demodulate(frame_bgr)
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

    # --- Matplotlib 4-panel figure ---
    fig = plt.figure(figsize=(16, 10), facecolor="#0d1117")
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.30)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    for ax in [ax1, ax2, ax3, ax4]:
        ax.set_facecolor("#161b22")
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        ax.tick_params(colors="#8b949e", labelsize=8)
        ax.xaxis.label.set_color("#8b949e")
        ax.yaxis.label.set_color("#8b949e")
        ax.title.set_color("#e6edf3")

    # --- Panel 1: Frame + RoI bbox ---
    ax1.imshow(frame_rgb)
    ax1.set_title(f"Stage 1 — Frame + RoI Localisation\n{fname}", fontsize=10, pad=4)
    ax1.axis("off")
    if result.roi_bbox is not None:
        x, y, w, h = result.roi_bbox
        col_mpl = "lime" if result.status == "LOCKED" else "yellow"
        rect = plt.Rectangle((x, y), w, h, linewidth=2, edgecolor=col_mpl, facecolor="none")
        ax1.add_patch(rect)
        ax1.text(x, max(y - 5, 10), result.status, color=col_mpl, fontsize=8,
                 fontweight="bold", va="bottom")

    # --- Panel 2: Zoomed RoI crop ---
    if result.roi_bbox is not None:
        bx, by, bw, bh = result.roi_bbox
        crop_bgr = frame_bgr[by : by + bh, bx : bx + bw]
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        ax2.imshow(crop_rgb, aspect="auto")
        # Overlay center scanlines
        for frac in [0.25, 0.5, 0.75]:
            ax2.axhline(frac * bh, color="cyan", linewidth=0.8, alpha=0.8)
        ax2.axvline(bw / 2, color="cyan", linewidth=0.8, alpha=0.8)
        ax2.set_title("Stage 2 — Zoomed RoI Stripes\n(cyan: sampling scanlines)", fontsize=10, pad=4)
        ax2.axis("off")
        ax2.set_xlabel(f"Stripe width ≈ {result.stripe_width_px:.1f} px/bit", fontsize=8)
    else:
        ax2.text(0.5, 0.5, "No RoI", ha="center", va="center",
                 color="red", fontsize=14, transform=ax2.transAxes)
        ax2.set_title("Stage 2 — Zoomed RoI", fontsize=10)

    # --- Panel 3: Waveform stages ---
    if result.raw_1d_signal.size > 0:
        raw  = result.raw_1d_signal
        base = result.baseline_curve
        det  = result.detrended_signal
        thr  = result.threshold_curve
        yy   = np.arange(len(raw))

        ax3_twin = ax3.twinx()

        # Raw + baseline on primary axis
        ax3.plot(yy, raw,  color="#58a6ff", linewidth=1.0, alpha=0.8, label="Raw I(y)")
        ax3.plot(yy, base, color="#ff7b72", linewidth=1.5, linestyle="--", label="Baseline")
        ax3.set_ylabel("Intensity", color="#58a6ff", fontsize=8)
        ax3.legend(loc="upper left", fontsize=7, facecolor="#161b22",
                   edgecolor="#30363d", labelcolor="#e6edf3")

        # Detrended + threshold on twin axis
        ax3_twin.plot(yy, det, color="#3fb950", linewidth=1.0, alpha=0.9, label="Detrended")
        ax3_twin.plot(yy, thr, color="#d29922", linewidth=1.0, linestyle=":", label="Threshold")
        ax3_twin.axhline(0, color="#8b949e", linewidth=0.5)

        # Bit sample markers
        if result.stripe_width_px > 0:
            n = len(det)
            pos = result.stripe_width_px / 2.0
            while pos < n:
                si = min(int(pos), n - 1)
                ax3_twin.plot(si, det[si], marker="x", color="#f85149",
                              markersize=5, markeredgewidth=1.2)
                pos += result.stripe_width_px

        ax3_twin.set_ylabel("Detrended", color="#3fb950", fontsize=8)
        ax3_twin.legend(loc="upper right", fontsize=7, facecolor="#161b22",
                        edgecolor="#30363d", labelcolor="#e6edf3")
        ax3_twin.tick_params(colors="#8b949e", labelsize=8)

        ax3.set_xlabel("Row index y (pixels)", fontsize=8)
        ax3.set_title("Stage 3 — Baseline Correction & EVA Binarisation\n"
                      "(× = bit sample markers)", fontsize=10, pad=4)
    else:
        ax3.text(0.5, 0.5, "No signal", ha="center", va="center",
                 color="gray", fontsize=14, transform=ax3.transAxes)
        ax3.set_title("Stage 3 — Waveform", fontsize=10)

    # --- Panel 4: Bitstream + Telemetry ---
    ax4.axis("off")
    ax4.set_title("Stage 4 — Preamble Sync, Bit Recovery & Telemetry", fontsize=10, pad=4)

    status_col = "#3fb950" if result.status == "LOCKED" else "#f85149"
    crc_col    = "#3fb950" if result.crc_valid else "#f85149"

    lines = [
        ("STATUS",           result.status,                              status_col),
        ("PREAMBLE",         "LOCKED" if result.preamble_offset >= 0
                              else "NO SYNC",                             status_col),
        ("NODE ID (dec)",    str(result.node_id)
                              if result.node_id is not None else "—",    "#58a6ff"),
        ("NODE ID (hex)",    f"0x{result.node_id:02X}"
                              if result.node_id is not None else "—",    "#58a6ff"),
        ("NODE ID (bin)",    result.node_id_bits or "—",                 "#58a6ff"),
        ("CRC recv'd",       result.crc_bits or "—",                     crc_col),
        ("CRC check",        "PASS ✓" if result.crc_valid else "FAIL ✗", crc_col),
        ("Packet (20b)",     result.packet_bits or "—",                  "#d29922"),
        ("Stripe px/bit",    f"{result.stripe_width_px:.2f}",            "#e6edf3"),
        ("Est. distance",    f"{result.estimated_dist_m:.2f} m",         "#e6edf3"),
        ("Latency",          f"{result.latency_ms:.2f} ms",              "#e6edf3"),
        ("Binary stream",    (result.binary_stream[:40] + "…")
                              if len(result.binary_stream) > 40
                              else result.binary_stream,                 "#8b949e"),
    ]

    y_start = 0.95
    dy      = 0.07
    for i, (label, value, col) in enumerate(lines):
        y = y_start - i * dy
        ax4.text(0.02, y, f"{label}:", transform=ax4.transAxes,
                 color="#8b949e", fontsize=9, va="top", fontfamily="monospace")
        ax4.text(0.40, y, str(value), transform=ax4.transAxes,
                 color=col, fontsize=9, va="top", fontfamily="monospace",
                 fontweight="bold" if i < 3 else "normal")

    # --- Suptitle ---
    fig.suptitle(
        f"OCC Rolling-Shutter Demodulator — 4-Stage Pipeline Breakdown\n"
        f"Frame: {fname}  |  Node {target_node}  |  Protocol v{gt.get('protocol_version','?')}",
        color="#e6edf3", fontsize=12, y=0.98,
    )

    # --- Save ---
    DOCS_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(fig_path), dpi=180, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[batch_eval] Pipeline figure saved → {fig_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCC Batch Evaluator & Pipeline Figure Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print detailed per-frame debug info.",
    )
    parser.add_argument(
        "--save-fig",
        type=Path,
        default=DEFAULT_FIG_PATH,
        help=f"Path to save the 4-stage pipeline figure (default: {DEFAULT_FIG_PATH}).",
    )
    parser.add_argument(
        "--roi-threshold", type=int, default=60,
        help="Brightness threshold for Stage 1 RoI detection (default 60).",
    )
    parser.add_argument(
        "--no-fig", action="store_true",
        help="Skip figure generation (evaluation only).",
    )
    args = parser.parse_args()

    demod = OCCDemodulator(roi_threshold=args.roi_threshold)

    t0 = time.perf_counter()
    results, accuracy = run_batch(demod, verbose=args.verbose)
    elapsed = time.perf_counter() - t0
    n = len(results)

    if n > 0:
        latencies = [r["latency_ms"] for r in results]
        mean_lat  = sum(latencies) / n
        min_lat   = min(latencies)
        max_lat   = max(latencies)
        fps_equiv = 1000.0 / mean_lat if mean_lat > 0 else 0.0
        print(f"  Latency  —  mean: {mean_lat:.1f} ms  "
              f"min: {min_lat:.1f} ms  max: {max_lat:.1f} ms  "
              f"≈ {fps_equiv:.1f} FPS equivalent")
        print(f"  Total batch time: {elapsed:.2f} s for {n} frames\n")

    if not args.no_fig:
        save_pipeline_figure(demod, target_node=105, fig_path=args.save_fig)

    # Exit with non-zero if accuracy < 100%
    if accuracy < 100.0:
        print(f"[batch_eval] WARNING: accuracy {accuracy:.1f}% < 100%", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
