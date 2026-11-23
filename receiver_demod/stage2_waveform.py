"""
stage2_waveform.py — Stage 2: 2D-to-1D Spatial Waveform Extraction
@cv-demod-agent | FYP_Project/receiver_demod/

Performs:
  1. Horizontal cross-row intensity averaging across the middle 60% width
     of the cropped RoI: I_bar(y) = (1 / W_eff) * sum_x I(x, y).
  2. 1D Gaussian/box smoothing (kernel=3) to suppress sensor noise without
     blurring bit transitions.
"""

from __future__ import annotations
import cv2
import numpy as np


def extract_waveform(roi_crop: np.ndarray, middle_frac: float = 0.60) -> np.ndarray:
    """
    Collapses 2D spatial RoI into a 1D temporal-equivalent intensity profile.

    Parameters
    ----------
    roi_crop : np.ndarray
        Cropped RoI image (Grayscale or BGR).
    middle_frac : float
        Fraction of central width to average across (default 0.60 = middle 60%).

    Returns
    -------
    raw_1d_signal : np.ndarray
        Float32 1D array of row-averaged intensities of length h.
    """
    if roi_crop is None or roi_crop.size == 0:
        return np.array([], dtype=np.float32)

    if roi_crop.ndim == 3:
        roi_gray = cv2.cvtColor(roi_crop, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi_crop

    h, w = roi_gray.shape[:2]

    # Select middle 60% width columns
    margin = (1.0 - middle_frac) / 2.0
    x0 = max(int(w * margin), 0)
    x1 = min(int(w * (1.0 - margin)), w)
    if x1 <= x0:
        x0, x1 = 0, w

    band = roi_gray[:, x0:x1].astype(np.float32)

    # Cross-row horizontal average
    raw_profile = band.mean(axis=1)

    # Light 1D Gaussian smoothing (kernel=3) to suppress sensor shot noise
    if len(raw_profile) >= 3:
        smoothed = cv2.GaussianBlur(raw_profile.reshape(-1, 1), (1, 3), 0).flatten()
    else:
        smoothed = raw_profile

    return smoothed.astype(np.float32)
