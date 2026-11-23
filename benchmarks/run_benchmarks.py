"""
run_benchmarks.py — Automated Stress-Test & Latency Benchmark Runner
@benchmark-agent | FYP_Project/benchmarks/

Executes:
  1. Sweep A: BER & PRR vs. Distance (2m to 20m in 2m steps, baseline noise=10).
  2. Sweep B: Stage 3 Baseline Detrending Ablation across Noise Levels (0 to 45 at 8m).
  3. Sweep C: False-Positive Rejection Test (100 unmodulated headlight frames).

Saves outputs to:
  - benchmarks/results.json
  - benchmarks/data/ber_results.csv

Usage:
  python3 benchmarks/run_benchmarks.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from transmitter_sim.channel_model import RollingShutterSimulator
from transmitter_sim.packet_encoder import build_packet
from receiver_demod.demodulator import OCCDemodulator, DemodResult

BENCHMARKS_DIR = _REPO_ROOT / "benchmarks"
DATA_DIR = BENCHMARKS_DIR / "data"
RESULTS_JSON_PATH = BENCHMARKS_DIR / "results.json"
BER_CSV_PATH = DATA_DIR / "ber_results.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def count_bit_errors(transmitted_bits: str, received_bits: str) -> int:
    """Computes Hamming distance between transmitted and received 20-bit packets."""
    if not received_bits or len(received_bits) != len(transmitted_bits):
        return len(transmitted_bits)
    return sum(1 for t, r in zip(transmitted_bits, received_bits) if t != r)


def run_sweep_a(
    sim: RollingShutterSimulator,
    demod: OCCDemodulator,
    distances: List[float],
    frames_per_point: int = 50,
    noise_level: float = 10.0,
    target_node: int = 105,
) -> List[Dict[str, Any]]:
    """Sweep A: Bit Error Rate & Packet Reception Rate vs. Distance."""
    print(f"\n{'='*75}")
    print(f"  SWEEP A: BER & PRR vs. Distance (2m–20m, Noise={noise_level}, N={frames_per_point}/point)")
    print(f"{'='*75}")
    print(f"  {'Dist(m)':<8} {'LED(px)':<8} {'PRR(%)':<9} {'BER':<10} {'Latency(ms)':<13} {'Status'}")
    print(f"  {'-'*7}  {'-'*7}  {'-'*8}  {'-'*9}  {'-'*12}  {'-'*15}")

    rng = np.random.default_rng(42)
    tx_packet = build_packet(target_node)
    sweep_results = []

    for d in distances:
        total_bit_errors = 0
        total_bits = frames_per_point * 20
        successful_packets = 0
        latencies = []
        led_px = sim.get_led_px_diameter(d)

        for i in range(frames_per_point):
            phase = int(rng.integers(0, 320))
            frame = sim.render(
                node_id=target_node,
                distance_m=d,
                noise_level=noise_level,
                phase_shift_px=phase,
                unmodulated_mode=False,
                seed=int(rng.integers(0, 100000)),
            )

            res: DemodResult = demod.demodulate(frame)
            latencies.append(res.latency_ms)

            # Check PRR criteria: locked, correct node, valid CRC
            is_valid_packet = (
                res.status == "LOCKED"
                and res.node_id == target_node
                and res.crc_valid
            )
            if is_valid_packet:
                successful_packets += 1
                rx_packet = res.packet_bits
            else:
                rx_packet = ""

            total_bit_errors += count_bit_errors(tx_packet, rx_packet)

        prr = (successful_packets / frames_per_point) * 100.0
        ber = total_bit_errors / total_bits
        mean_lat = float(np.mean(latencies))

        status_str = "RELIABLE" if prr >= 90.0 else ("DEGRADED" if prr > 0 else "OUT_OF_RANGE")
        print(f"  {d:<8.1f} {led_px:<8.1f} {prr:<9.1f} {ber:<10.4f} {mean_lat:<13.2f} {status_str}")

        sweep_results.append({
            "distance_m": float(d),
            "led_px_diameter": float(led_px),
            "prr_percent": float(prr),
            "ber": float(ber),
            "mean_latency_ms": float(mean_lat),
            "successful_packets": int(successful_packets),
            "total_frames": int(frames_per_point),
            "status": status_str,
        })

    return sweep_results


def run_sweep_b(
    sim: RollingShutterSimulator,
    noise_levels: List[float],
    distance_m: float = 8.0,
    frames_per_point: int = 50,
    target_node: int = 105,
) -> List[Dict[str, Any]]:
    """Sweep B: Baseline Detrending Ablation Study across Noise Levels."""
    print(f"\n{'='*75}")
    print(f"  SWEEP B: Baseline Detrending Ablation at d={distance_m}m across Noise Levels")
    print(f"{'='*75}")
    print(f"  {'Noise Sigma':<12} {'With Detrending (%)':<22} {'Without Detrending (%)':<24} {'Gain (%)'}")
    print(f"  {'-'*11}  {'-'*21}  {'-'*23}  {'-'*8}")

    rng = np.random.default_rng(99)
    demod_with = OCCDemodulator(enable_detrending=True)
    demod_without = OCCDemodulator(enable_detrending=False)
    ablation_results = []

    for sigma in noise_levels:
        success_with = 0
        success_without = 0

        for i in range(frames_per_point):
            phase = int(rng.integers(0, 320))
            frame = sim.render(
                node_id=target_node,
                distance_m=distance_m,
                noise_level=sigma,
                phase_shift_px=phase,
                unmodulated_mode=False,
                seed=int(rng.integers(0, 100000)),
            )

            # Test with Stage 3 polynomial baseline detrending
            res_w = demod_with.demodulate(frame)
            if res_w.status == "LOCKED" and res_w.node_id == target_node and res_w.crc_valid:
                success_with += 1

            # Test without detrending (ablation mode: raw global thresholding)
            res_wo = demod_without.demodulate(frame)
            if res_wo.status == "LOCKED" and res_wo.node_id == target_node and res_wo.crc_valid:
                success_without += 1

        acc_w = (success_with / frames_per_point) * 100.0
        acc_wo = (success_without / frames_per_point) * 100.0
        gain = acc_w - acc_wo

        print(f"  {sigma:<12.1f} {acc_w:<22.1f} {acc_wo:<24.1f} +{gain:<7.1f}")

        ablation_results.append({
            "noise_level": float(sigma),
            "accuracy_with_detrending_percent": float(acc_w),
            "accuracy_without_detrending_percent": float(acc_wo),
            "gain_percent": float(gain),
            "frames_tested": int(frames_per_point),
        })

    return ablation_results


def run_sweep_c(
    sim: RollingShutterSimulator,
    demod: OCCDemodulator,
    num_frames: int = 100,
) -> Dict[str, Any]:
    """Sweep C: False-Positive Rejection Test on Unmodulated Headlights."""
    print(f"\n{'='*75}")
    print(f"  SWEEP C: False-Positive Rejection on Unmodulated Lights (N={num_frames} frames)")
    print(f"{'='*75}")

    rng = np.random.default_rng(777)
    false_positive_locks = 0
    rejected_frames = 0
    latencies = []

    for i in range(num_frames):
        d = float(rng.uniform(2.0, 20.0))
        noise = float(rng.uniform(5.0, 30.0))
        phase = int(rng.integers(0, 320))

        frame = sim.render(
            node_id=0,
            distance_m=d,
            noise_level=noise,
            phase_shift_px=phase,
            unmodulated_mode=True,
            seed=int(rng.integers(0, 100000)),
        )

        res = demod.demodulate(frame)
        latencies.append(res.latency_ms)

        if res.status == "LOCKED" and res.crc_valid:
            false_positive_locks += 1
        else:
            rejected_frames += 1

    fp_rate = (false_positive_locks / num_frames) * 100.0
    rejection_rate = (rejected_frames / num_frames) * 100.0
    mean_lat = float(np.mean(latencies))

    print(f"  Total Headlight Frames Tested : {num_frames}")
    print(f"  Correctly Rejected Frames     : {rejected_frames} ({rejection_rate:.1f}%)")
    print(f"  False-Positive Locks          : {false_positive_locks} ({fp_rate:.1f}%)")
    print(f"  Average Processing Latency    : {mean_lat:.2f} ms")
    print(f"  Rejection Verification Status : {'PASS (100% REJECTION)' if fp_rate == 0.0 else 'FAIL'}")

    return {
        "num_frames_tested": int(num_frames),
        "rejected_frames": int(rejected_frames),
        "false_positive_locks": int(false_positive_locks),
        "false_positive_rate_percent": float(fp_rate),
        "rejection_rate_percent": float(rejection_rate),
        "mean_latency_ms": float(mean_lat),
        "passed": bool(fp_rate == 0.0),
    }


def save_csv(sweep_a_results: List[Dict[str, Any]], csv_path: Path) -> None:
    """Exports Sweep A results to CSV format."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "distance_m",
        "led_px_diameter",
        "prr_percent",
        "ber",
        "mean_latency_ms",
        "successful_packets",
        "total_frames",
        "status",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sweep_a_results)
    print(f"\n[✓] Exported BER results to CSV → {csv_path}")


def save_results_json(all_results: Dict[str, Any], json_path: Path) -> None:
    """Saves complete benchmark metrics to JSON."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"[✓] Exported complete benchmark results → {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OCC Automated Stress-Test & Latency Benchmark Runner")
    parser.add_argument("--frames-per-point", type=int, default=50, help="Number of frames per sweep point (default 50)")
    parser.add_argument("--fast", action="store_true", help="Fast smoke test mode with fewer frames")
    args = parser.parse_args()

    n_frames = 10 if args.fast else args.frames_per_point
    n_headlights = 20 if args.fast else 100

    print("=" * 75)
    print("  OCC BENCHMARK RUNNER (@benchmark-agent)")
    print(f"  Configuration: {n_frames} frames/point, {n_headlights} headlight test frames")
    print("=" * 75)

    sim = RollingShutterSimulator(add_clutter=True)
    demod = OCCDemodulator()

    distances = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    noise_levels = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0]

    t_start = time.perf_counter()

    # 1. Sweep A
    sweep_a = run_sweep_a(sim, demod, distances, frames_per_point=n_frames, noise_level=10.0, target_node=105)

    # 2. Sweep B
    sweep_b = run_sweep_b(sim, noise_levels, distance_m=8.0, frames_per_point=n_frames, target_node=105)

    # 3. Sweep C
    sweep_c = run_sweep_c(sim, demod, num_frames=n_headlights)

    total_time_s = time.perf_counter() - t_start

    # Summary metrics calculation
    prr_12m = np.mean([r["prr_percent"] for r in sweep_a if r["distance_m"] <= 12.0])
    max_reliable_range = max([r["distance_m"] for r in sweep_a if r["prr_percent"] >= 90.0], default=0.0)
    all_latencies = [r["mean_latency_ms"] for r in sweep_a]
    overall_mean_latency = float(np.mean(all_latencies))
    fps_equiv = 1000.0 / overall_mean_latency if overall_mean_latency > 0 else 0.0

    summary_metrics = {
        "prr_at_12m_percent": float(prr_12m),
        "max_reliable_range_m": float(max_reliable_range),
        "overall_mean_latency_ms": float(overall_mean_latency),
        "fps_equivalent": float(fps_equiv),
        "false_positive_rejection_rate_percent": float(sweep_c["rejection_rate_percent"]),
        "total_benchmark_runtime_s": float(total_time_s),
    }

    full_payload = {
        "summary": summary_metrics,
        "sweep_a_ber_prr_vs_distance": sweep_a,
        "sweep_b_detrending_ablation": sweep_b,
        "sweep_c_headlight_rejection": sweep_c,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "protocol_version": "1.1",
    }

    save_csv(sweep_a, BER_CSV_PATH)
    save_results_json(full_payload, RESULTS_JSON_PATH)

    print(f"\n{'='*75}")
    print(f"  BENCHMARK SUITE COMPLETE in {total_time_s:.1f} s")
    print(f"  PRR (d <= 12m)          : {prr_12m:.1f}%")
    print(f"  Max Reliable Range      : {max_reliable_range:.1f} m")
    print(f"  Mean Latency / FPS      : {overall_mean_latency:.2f} ms ({fps_equiv:.1f} FPS)")
    print(f"  False-Positive Rejection: {sweep_c['rejection_rate_percent']:.1f}%")
    print(f"{'='*75}\n")


if __name__ == "__main__":
    main()
