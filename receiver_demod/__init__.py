"""
receiver_demod — 4-Stage OCC Demodulator & Visual HUD
@cv-demod-agent | FYP_Project/receiver_demod/

Modules:
  - stage1_roi.py       : RoI Extraction & Transmitter Localization
  - stage2_waveform.py  : 2D-to-1D Spatial Waveform Extraction
  - stage3_binarize.py  : Baseline Correction & Adaptive Binarization
  - stage4_decoder.py   : Stripe Width Estimation, Preamble Sync & Bit Recovery
  - demodulator.py      : OCCDemodulator class & DemodResult dataclass
  - hud_display.py      : 4-Quadrant Real-Time Visual HUD
  - run_receiver.py     : Live & Single-Image CLI runner
  - batch_eval.py       : Dataset batch verification & slide asset generator
"""

from receiver_demod.demodulator import OCCDemodulator, DemodResult
from receiver_demod.stage1_roi import extract_roi
from receiver_demod.stage2_waveform import extract_waveform
from receiver_demod.stage3_binarize import baseline_and_binarize
from receiver_demod.stage4_decoder import decode_packet, compute_crc4, build_full_packet
from receiver_demod.hud_display import build_hud

__all__ = [
    "OCCDemodulator",
    "DemodResult",
    "extract_roi",
    "extract_waveform",
    "baseline_and_binarize",
    "decode_packet",
    "compute_crc4",
    "build_full_packet",
    "build_hud",
]
