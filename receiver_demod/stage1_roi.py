"""
stage1_roi.py — Stage 1: RoI Extraction & Transmitter Localization
@cv-demod-agent | FYP_Project/receiver_demod/

Performs:
  1. Grayscale conversion.
  2. Multi-thresholding + vertical morphological closing (merges OOK dark stripes).
  3. Contour detection and luminaire RoI localization.
  4. Active central region cropping to discard circular edge drop-off.
  5. Distance estimation via camera pinhole geometry: d = (f * D_real) / h_px.
"""

from __future__ import annotations
from typing import Optional, Tuple
import cv2
import numpy as np

# Optical parameters from shared/protocol.json
FOCAL_LENGTH_PX: float = 1200.0   # f (px)
PHYSICAL_DIAM_M: float = 0.25     # D_real (m)


def extract_roi(
    frame: np.ndarray,
    min_area_px: int = 15,
    max_area_frac: float = 0.25,
) -> Tuple[Optional[Tuple[int, int, int, int]], Optional[np.ndarray], float]:
    """
    Locates the primary streetlight LED in the frame and crops its inner stripe region.

    Parameters
    ----------
    frame : np.ndarray
        Input 1920x1080 BGR or Grayscale frame.
    min_area_px : int
        Minimum contour bounding box area to accept.
    max_area_frac : float
        Maximum fraction of frame area to prevent full-frame false matches.

    Returns
    -------
    roi_bbox : Optional[Tuple[int, int, int, int]]
        Bounding box (x, y, w, h) in original frame coordinates, or None.
    roi_crop : Optional[np.ndarray]
        Cropped active stripe region, or None.
    estimated_dist_m : float
        Estimated distance in metres based on observed RoI height.
    """
    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame.copy()

    h_frame, w_frame = gray.shape[:2]
    cx_frame = w_frame // 2  # 960
    cy_frame = h_frame // 2  # 540

    # Mask out bottom banner overlay if present (y >= 1000) so label text
    # doesn't interfere with luminaire localization
    search_gray = gray.copy()
    if h_frame >= 1000:
        search_gray[1000:, :] = 0

    best_bbox: Optional[Tuple[int, int, int, int]] = None
    min_center_dist: float = 1e9

    # Try decreasing brightness thresholds to locate LED at any distance (3m to 18m)
    for thresh in [40, 30, 25, 20]:
        _, mask = cv2.threshold(search_gray, thresh, 255, cv2.THRESH_BINARY)

        # Vertical morphological closing: merges horizontal dark stripes into a solid blob
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 35))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        candidates = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            if area < min_area_px or area > (w_frame * h_frame * max_area_frac):
                continue
            ar = w / float(h)
            if not (0.25 <= ar <= 4.0):
                continue
            # Distance from expected luminaire position (frame center)
            dist = np.hypot((x + w / 2.0) - cx_frame, (y + h / 2.0) - cy_frame)
            candidates.append((dist, (x, y, w, h)))

        if candidates:
            candidates.sort(key=lambda item: item[0])
            best_dist, bbox = candidates[0]
            if best_dist < min_center_dist:
                min_center_dist = best_dist
                best_bbox = bbox
            break

    # Fallback if no contour was picked up (e.g. extremely faint or saturated)
    if best_bbox is None:
        win_w, win_h = 100, 100
        x0 = max(cx_frame - win_w // 2, 0)
        y0 = max(cy_frame - win_h // 2, 0)
        center_patch = search_gray[y0 : y0 + win_h, x0 : x0 + win_w]
        if center_patch.max() > 10:
            best_bbox = (x0, y0, win_w, win_h)

    if best_bbox is None:
        return None, None, 0.0

    x, y, w, h = best_bbox

    # Estimate distance using pinhole camera model
    estimated_dist_m = (PHYSICAL_DIAM_M * FOCAL_LENGTH_PX) / float(max(h, 1))

    # Crop inner active stripe region: discard outer 20% on left and right
    # to avoid circular Gaussian beam edge drop-off and maximize SNR
    shrink_x = max(int(w * 0.20), 1)
    xi = max(x + shrink_x, 0)
    yi = max(y, 0)
    wi = max(w - 2 * shrink_x, 4)
    hi = max(h, 4)

    xi = min(xi, w_frame - wi)
    yi = min(yi, h_frame - hi)

    roi_crop = gray[yi : yi + hi, xi : xi + wi].copy()
    return (x, y, w, h), roi_crop, float(estimated_dist_m)
