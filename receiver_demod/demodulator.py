"""
demodulator.py — 4-Stage OCC Rolling-Shutter Demodulator
@cv-demod-agent | FYP_Project/receiver_demod/

Implements OCCDemodulator: a modular, protocol-compliant demodulation engine that
processes a 1920×1080 BGR or grayscale frame through four stages and returns a
structured DemodResult with all intermediate signals for the HUD and benchmarking.

Compatible with: shared/protocol.json v1.1 | @sim-agent packet format (20 bits cyclic)

Packet layout (frozen, per ARCHITECTURE.md §6.1):
  Bits  0– 7 : PREAMBLE  = 10101010 (0xAA)
  Bits  8–15 : NODE_ID   = 8-bit integer identifier
  Bits 16–19 : CRC_4-ITU = polynomial 0x13, computed over bits 0–15

Stages:
  Stage 1 : RoI Extraction & Transmitter Localization (stage1_roi.py)
  Stage 2 : 2D-to-1D Spatial Waveform Extraction (stage2_waveform.py)
  Stage 3 : Baseline Correction & Adaptive Binarization (stage3_binarize.py)
  Stage 4 : Stripe Width Estimation, Preamble Sync & Bit Recovery (stage4_decoder.py)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np

from receiver_demod.stage1_roi import extract_roi
from receiver_demod.stage2_waveform import extract_waveform
from receiver_demod.stage3_binarize import baseline_and_binarize
from receiver_demod.stage4_decoder import decode_packet, compute_crc4, PREAMBLE_STR


@dataclass
class DemodResult:
    """
    Structured output of OCCDemodulator.demodulate().

    Fields
    ------
    roi_bbox         : (x, y, w, h) bounding box in original frame, or None
    raw_1d_signal    : Row-averaged intensity profile within the RoI (float32 array)
    baseline_curve   : Baseline fit of raw_1d_signal
    detrended_signal : raw_1d_signal - baseline_curve
    threshold_curve  : EVA adaptive threshold applied to detrended_signal
    binary_stream    : Binary string of recovered bits
    status           : "LOCKED" | "CRC_ERROR" | "REJECTED (NO PREAMBLE)" | "NO_ROI"
    node_id          : Decoded integer node ID, or None
    node_id_bits     : 8-bit binary string of node_id, or ""
    crc_bits         : Received 4-bit CRC string, or ""
    crc_valid        : True if CRC passes, False otherwise
    latency_ms       : Total processing latency in milliseconds
    preamble_offset  : Index into binary_stream where preamble was found
    stripe_width_px  : Estimated stripe width (pixels per bit)
    estimated_dist_m : Distance estimate from RoI height via pinhole model
    packet_bits      : Full recovered 20-bit packet string (or "")
    """
    roi_bbox         : Optional[Tuple[int, int, int, int]] = None
    raw_1d_signal    : np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    baseline_curve   : np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    detrended_signal : np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    threshold_curve  : np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    binary_stream    : str = ""
    status           : str = "NO_ROI"
    node_id          : Optional[int] = None
    node_id_bits     : str = ""
    crc_bits         : str = ""
    crc_valid        : bool = False
    latency_ms       : float = 0.0
    preamble_offset  : int = -1
    stripe_width_px  : float = 0.0
    estimated_dist_m : float = 0.0
    packet_bits      : str = ""


class OCCDemodulator:
    """
    4-Stage rolling-shutter OCC demodulator.
    """

    def __init__(
        self,
        roi_threshold: int = 40,
        poly_degree: int = 2,
        eva_window: int = 20,
    ):
        self.roi_threshold = roi_threshold
        self.poly_degree = poly_degree
        self.eva_window = eva_window

    def demodulate(self, frame: np.ndarray) -> DemodResult:
        """
        Processes one BGR or Grayscale frame through the 4-stage demodulation pipeline.
        """
        t_start = time.perf_counter()
        result = DemodResult()

        if frame is None or frame.size == 0:
            result.status = "NO_ROI"
            result.latency_ms = (time.perf_counter() - t_start) * 1000.0
            return result

        # --- Stage 1: RoI Extraction & Transmitter Localization ---
        roi_bbox, roi_crop, dist_m = extract_roi(frame)
        if roi_bbox is None or roi_crop is None or roi_crop.size == 0:
            result.status = "NO_ROI"
            result.latency_ms = (time.perf_counter() - t_start) * 1000.0
            return result

        result.roi_bbox = roi_bbox
        result.estimated_dist_m = dist_m

        # --- Stage 2: 2D-to-1D Spatial Waveform Extraction ---
        raw_signal = extract_waveform(roi_crop, middle_frac=0.60)
        result.raw_1d_signal = raw_signal

        # --- Stage 3: Baseline Correction & Adaptive Binarization ---
        baseline, detrended, threshold, binary_arr = baseline_and_binarize(
            raw_signal, poly_degree=self.poly_degree, eva_window=self.eva_window
        )
        result.baseline_curve = baseline
        result.detrended_signal = detrended
        result.threshold_curve = threshold
        result.binary_stream = "".join(str(b) for b in binary_arr)

        # --- Stage 4: Stripe Width, Preamble Sync & Bit Recovery ---
        (
            status,
            node_id,
            node_id_bits,
            crc_bits,
            crc_valid,
            stripe_px,
            p_offset,
            pkt_bits,
        ) = decode_packet(frame, raw_signal, detrended, binary_arr, dist_m)

        result.status = status
        result.node_id = node_id
        result.node_id_bits = node_id_bits
        result.crc_bits = crc_bits
        result.crc_valid = crc_valid
        result.stripe_width_px = stripe_px
        result.preamble_offset = p_offset
        result.packet_bits = pkt_bits

        result.latency_ms = (time.perf_counter() - t_start) * 1000.0
        return result
