"""
stage3_binarize.py — Stage 3: Baseline Correction & Adaptive Binarization
@cv-demod-agent | FYP_Project/receiver_demod/

Performs:
  1. Low-order polynomial fitting (degree 2 or 3) to model the LED's Gaussian beam falloff.
  2. Baseline subtraction to produce a zero-mean flattened waveform S_flat(y).
  3. Extreme Value Averaging (EVA) sliding-window thresholding:
     theta(y) = (V_local_max(y) + V_local_min(y)) / 2.
  4. Adaptive binarization of S_flat(y) into clean square-wave bit pulses.
"""

from __future__ import annotations
from typing import Tuple
import numpy as np


def baseline_and_binarize(
    signal: np.ndarray,
    poly_degree: int = 2,
    eva_window: int = 20,
    enable_detrending: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Fits baseline envelope, detrends, and adaptively binarizes 1D waveform.

    Parameters
    ----------
    signal : np.ndarray
        Float32 1D raw intensity signal from Stage 2.
    poly_degree : int
        Polynomial degree for baseline fitting (default 2).
    eva_window : int
        Sliding window size in rows for local min/max Extreme Value Averaging.
    enable_detrending : bool
        If True, fits polynomial baseline and uses EVA adaptive thresholding.
        If False, uses raw global thresholding (ablation mode).

    Returns
    -------
    baseline_curve : np.ndarray
        Fitted low-frequency baseline envelope.
    detrended_signal : np.ndarray
        Flattened signal: S_flat(y) = signal(y) - baseline(y).
    threshold_curve : np.ndarray
        Dynamic EVA threshold curve theta(y).
    binary_array : np.ndarray
        Binary pulse train (int8 array containing 0s and 1s).
    """
    n = len(signal)
    if n == 0:
        empty = np.array([], dtype=np.float32)
        return empty, empty, empty, np.array([], dtype=np.int8)

    y_idx = np.arange(n, dtype=np.float64)

    if enable_detrending:
        # 1. Polynomial baseline estimation
        try:
            deg = min(poly_degree, max(n - 1, 1))
            coeffs = np.polyfit(y_idx, signal.astype(np.float64), deg)
            baseline_curve = np.polyval(coeffs, y_idx).astype(np.float32)
        except Exception:
            w_ma = max(int(n * 0.35), 3) | 1
            baseline_curve = np.convolve(signal, np.ones(w_ma) / w_ma, mode="same").astype(np.float32)

        # 2. Baseline subtraction (detrending)
        detrended_signal = (signal - baseline_curve).astype(np.float32)

        # 3. Extreme Value Averaging (EVA) sliding-window thresholding
        win = max(min(eva_window, n), 3)
        half_w = win // 2

        local_max = np.zeros(n, dtype=np.float32)
        local_min = np.zeros(n, dtype=np.float32)

        for i in range(n):
            lo = max(0, i - half_w)
            hi = min(n, i + half_w + 1)
            chunk = detrended_signal[lo:hi]
            local_max[i] = chunk.max()
            local_min[i] = chunk.min()

        threshold_curve = ((local_max + local_min) * 0.5).astype(np.float32)

        # 4. Adaptive binarization into square wave
        binary_array = (detrended_signal >= threshold_curve).astype(np.int8)
    else:
        # Ablation mode: raw global mean thresholding without baseline removal
        global_mean = float(signal.mean())
        baseline_curve = np.full(n, global_mean, dtype=np.float32)
        detrended_signal = (signal - global_mean).astype(np.float32)
        threshold_curve = np.zeros(n, dtype=np.float32)
        binary_array = (detrended_signal >= 0).astype(np.int8)

    return baseline_curve, detrended_signal, threshold_curve, binary_array
