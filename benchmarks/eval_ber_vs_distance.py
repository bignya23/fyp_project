"""
eval_ber_vs_distance.py — Distance Sweep & BER Evaluator
@benchmark-agent | FYP_Project/benchmarks/

Executes synthetic sweeps across distances d in [2m, 20m] and exports
metrics to benchmarks/data/ber_results.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from transmitter_sim.channel_model import RollingShutterSimulator
from receiver_demod.demodulator import OCCDemodulator
from benchmarks.run_benchmarks import run_sweep_a, save_csv, BER_CSV_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate BER and PRR vs. Distance")
    parser.add_argument("--frames-per-point", type=int, default=50, help="Frames per distance point (default 50)")
    parser.add_argument("--noise-level", type=float, default=10.0, help="Readout noise sigma (default 10.0)")
    args = parser.parse_args()

    sim = RollingShutterSimulator(add_clutter=True)
    demod = OCCDemodulator()
    distances = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]

    sweep_a = run_sweep_a(
        sim,
        demod,
        distances,
        frames_per_point=args.frames_per_point,
        noise_level=args.noise_level,
    )
    save_csv(sweep_a, BER_CSV_PATH)


if __name__ == "__main__":
    main()
