"""
channel_model.py — Rolling-Shutter OCC Channel Simulator
@sim-agent | FYP_Project/transmitter_sim/

Implements RollingShutterSimulator: a physics-based synthetic frame generator that
renders a 1920×1080 BGR frame of a modulated LED streetlamp as seen through a
rolling-shutter CMOS camera sensor.

Physics Chain:
  1.  Pinhole projection: LED physical diameter → pixel footprint at given distance
  2.  Gaussian beam profile: 2D spatial intensity falloff across the LED aperture
  3.  OOK temporal-to-spatial striping: 20-bit cyclic packet mapped row-by-row
  4.  Ambient urban glow, sensor readout noise, optional clutter
  5.  Unmodulated headlight mode (for false-positive rejection testing)

Usage:
    sim = RollingShutterSimulator()
    frame = sim.render(node_id=105, distance_m=5.0, noise_level=10,
                       phase_shift_px=0, unmodulated_mode=False)
"""

import json
import math
import os
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from transmitter_sim.packet_encoder import build_packet

# ---------------------------------------------------------------------------
# Load shared protocol contract
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROTOCOL_PATH = _REPO_ROOT / "shared" / "protocol.json"

with open(_PROTOCOL_PATH, "r") as _fh:
    PROTOCOL = json.load(_fh)

# Convenience aliases from protocol
_LED = PROTOCOL["led_specs"]
_CAM = PROTOCOL["camera_and_optical_specs"]
_PIN = _CAM["pinhole_model"]

FRAME_W: int = _CAM["frame_resolution"]["width"]   # 1920
FRAME_H: int = _CAM["frame_resolution"]["height"]  # 1080
FOCAL_LENGTH_PX: float = _PIN["focal_length_px"]   # 1200 px
PHYSICAL_DIAMETER_M: float = _PIN["physical_led_diameter_m"]  # 0.25 m
ROW_READOUT_US: float = _LED["row_readout_time_us"]  # 25.0 µs
LED_FREQ_HZ: float = _LED["led_modulation_freq_hz"]  # 2500 Hz
OOK_HIGH: float = _LED["ook_high_state"]   # 1.0
OOK_LOW: float = _LED["ook_low_state"]     # 0.1

# Baseline pixels-per-bit at the protocol's nominal frequency
# W_pixels = 1 / (2 * f_led * t_row)   — full cycle = 2 half-cycles (high + low)
# Using symbol period: T_b = 1/f_led => px_per_bit = T_b / t_row_s
BASELINE_PX_PER_BIT: float = 1.0 / (LED_FREQ_HZ * ROW_READOUT_US * 1e-6)  # = 8 rows


# ---------------------------------------------------------------------------
# Helper: generate a dark urban night-sky / tunnel background
# ---------------------------------------------------------------------------
def _make_background(rng: np.random.Generator) -> np.ndarray:
    """
    Create a 1920×1080 BGR background that looks like a dark urban night or tunnel.
    Consists of:
      - Very dark blue-grey base (~[8, 10, 6])
      - Subtle horizontal gradient (slightly brighter near horizon)
      - Random faint road-texture grain
    """
    base = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.float32)

    # Dark blue-grey ambient colour (B, G, R)
    base[:, :] = [12.0, 10.0, 7.0]

    # Subtle vertical gradient — slightly lighter near the vertical centre
    grad = np.linspace(0.0, 6.0, FRAME_H, dtype=np.float32)
    grad = np.abs(grad - grad.mean())          # peak at middle rows
    grad = (6.0 - grad).clip(0, 6)[:, None, None]
    base += grad

    # Very faint road-texture grain
    grain = rng.normal(0.0, 1.5, (FRAME_H, FRAME_W, 3)).astype(np.float32)
    base = (base + grain).clip(0, 255)

    return base


# ---------------------------------------------------------------------------
# Helper: optional secondary background clutter blob
# ---------------------------------------------------------------------------
def _add_clutter_blobs(canvas: np.ndarray, rng: np.random.Generator) -> None:
    """
    Add 1-2 dim distant static streetlamp / tail-light blobs away from the
    frame centre. Operates in-place on the float32 canvas.
    """
    # Tail-light blob — lower-right quadrant, red tint
    cx, cy = int(FRAME_W * 0.78), int(FRAME_H * 0.68)
    blob_r = 12
    yy, xx = np.ogrid[:FRAME_H, :FRAME_W]
    dist2 = (xx - cx) ** 2 + (yy - cy) ** 2
    mask = np.exp(-dist2 / (2 * (blob_r * 0.6) ** 2)).astype(np.float32)
    canvas[:, :, 0] += mask * 8    # B
    canvas[:, :, 1] += mask * 4    # G
    canvas[:, :, 2] += mask * 25   # R — red tail-light

    # Distant streetlamp — upper-left, warm yellow
    cx2, cy2 = int(FRAME_W * 0.15), int(FRAME_H * 0.32)
    blob_r2 = 8
    dist2b = (xx - cx2) ** 2 + (yy - cy2) ** 2
    mask2 = np.exp(-dist2b / (2 * (blob_r2 * 0.6) ** 2)).astype(np.float32)
    canvas[:, :, 0] += mask2 * 10   # B
    canvas[:, :, 1] += mask2 * 20   # G
    canvas[:, :, 2] += mask2 * 22   # R — warm yellow


# ---------------------------------------------------------------------------
# Main Simulator Class
# ---------------------------------------------------------------------------

class RollingShutterSimulator:
    """
    Physics-based synthetic rolling-shutter OCC frame generator.

    Instantiation loads the shared protocol.json contract once. Each call to
    ``render()`` produces a fresh 1920×1080 uint8 BGR frame.
    """

    def __init__(
        self,
        add_clutter: bool = True,
        pixels_per_bit: Optional[float] = None,
        led_centre: Optional[Tuple[int, int]] = None,
    ):
        """
        Args:
            add_clutter: If True, add dim background tail-light / streetlamp blobs.
            pixels_per_bit: Override the number of pixel rows per OOK bit.
                            Defaults to BASELINE_PX_PER_BIT (8) from protocol.
            led_centre: (cx, cy) pixel coordinate of LED centre.
                        Defaults to frame centre (960, 540).
        """
        self.add_clutter = add_clutter
        self.pixels_per_bit: float = pixels_per_bit if pixels_per_bit else BASELINE_PX_PER_BIT
        self.cx: int = led_centre[0] if led_centre else FRAME_W // 2   # 960
        self.cy: int = led_centre[1] if led_centre else FRAME_H // 2   # 540
        self._rng = np.random.default_rng(seed=None)   # fresh rng per instance

    # ------------------------------------------------------------------
    # Public: render one frame
    # ------------------------------------------------------------------

    def render(
        self,
        node_id: int = 105,
        distance_m: float = 5.0,
        noise_level: float = 10.0,
        phase_shift_px: int = 0,
        unmodulated_mode: bool = False,
        seed: Optional[int] = None,
    ) -> np.ndarray:
        """
        Render one synthetic rolling-shutter frame.

        Args:
            node_id: Integer transmitter ID [0, 255].
            distance_m: Transmitter distance in metres [0.5, 50].
            noise_level: Gaussian sensor noise standard deviation [0, 100].
            phase_shift_px: Vertical phase offset in pixels simulating async
                            frame start (shifts the stripe pattern up/down).
            unmodulated_mode: When True, render a solid Gaussian headlight
                              with NO data stripes (for false-positive testing).
            seed: Optional RNG seed for reproducibility.

        Returns:
            1920×1080 uint8 BGR numpy array.
        """
        if seed is not None:
            self._rng = np.random.default_rng(seed=seed)

        # 1. Project LED physical diameter → pixel footprint
        led_px_diameter = self._project_diameter(distance_m)

        # 2. Build dark background
        canvas = _make_background(self._rng)

        # 3. Add background clutter
        if self.add_clutter:
            _add_clutter_blobs(canvas, self._rng)

        # 4. Compute 2D Gaussian beam profile (shape mask, peak=1.0)
        gaussian_mask = self._build_gaussian_mask(led_px_diameter)

        # 5. Build intensity layer for the LED disc area
        if unmodulated_mode:
            led_layer = self._render_unmodulated(led_px_diameter, gaussian_mask)
        else:
            led_layer = self._render_ook_stripes(
                node_id, led_px_diameter, gaussian_mask, phase_shift_px
            )

        # 6. Add LED layer to canvas
        canvas = canvas + led_layer

        # 7. Add Gaussian sensor readout noise
        if noise_level > 0:
            noise = self._rng.normal(0.0, float(noise_level), canvas.shape).astype(np.float32)
            canvas = canvas + noise

        # 8. Clip and convert to uint8
        frame = np.clip(canvas, 0, 255).astype(np.uint8)
        return frame

    # ------------------------------------------------------------------
    # Physics helpers
    # ------------------------------------------------------------------

    def _project_diameter(self, distance_m: float) -> float:
        """
        Pinhole projection: physical LED diameter → pixel footprint.

        Formula: P_px = (D_physical_m * f_px) / d_m
        Clamps minimum to 4 px (sub-pixel LED still needs to be detectable).
        """
        if distance_m <= 0:
            distance_m = 0.1
        p_px = (PHYSICAL_DIAMETER_M * FOCAL_LENGTH_PX) / distance_m
        return max(p_px, 4.0)

    def _build_gaussian_mask(self, led_px_diameter: float) -> np.ndarray:
        """
        Build a 2D Gaussian spatial intensity mask over the full frame.

        The sigma is set to led_px_diameter / 4 so that the Gaussian is
        'tight' (falls to ~1/e² at the LED radius), giving a natural smooth
        falloff for the receiver's detrending stage.

        Returns:
            Float32 array of shape (H, W) with values in [0.0, 1.0].
        """
        sigma = max(led_px_diameter / 4.0, 1.5)
        yy, xx = np.ogrid[:FRAME_H, :FRAME_W]
        dist2 = ((xx - self.cx) ** 2 + (yy - self.cy) ** 2).astype(np.float32)
        mask = np.exp(-dist2 / (2.0 * sigma ** 2))
        return mask

    def _build_circular_disc_mask(self, led_px_diameter: float) -> np.ndarray:
        """
        Binary circular disc mask: 1 inside LED aperture, 0 outside.

        Returns:
            Float32 array of shape (H, W) with values in {0.0, 1.0}.
        """
        radius = led_px_diameter / 2.0
        yy, xx = np.ogrid[:FRAME_H, :FRAME_W]
        dist2 = ((xx - self.cx) ** 2 + (yy - self.cy) ** 2).astype(np.float32)
        disc = (dist2 <= radius ** 2).astype(np.float32)
        return disc

    def _render_unmodulated(
        self, led_px_diameter: float, gaussian_mask: np.ndarray
    ) -> np.ndarray:
        """
        Render a bright solid Gaussian headlight / streetlamp with NO stripes.

        Returns:
            Float32 BGR array of shape (H, W, 3).
        """
        disc = self._build_circular_disc_mask(led_px_diameter)

        # Peak brightness 230 (leaves headroom before clipping)
        I_peak = 230.0
        intensity = I_peak * gaussian_mask * disc

        # Warm white colour (slightly yellow-white headlight tint)
        layer = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.float32)
        layer[:, :, 0] = intensity * 0.95   # B
        layer[:, :, 1] = intensity * 1.00   # G
        layer[:, :, 2] = intensity * 0.90   # R (warm tint)
        return layer

    def _render_ook_stripes(
        self,
        node_id: int,
        led_px_diameter: float,
        gaussian_mask: np.ndarray,
        phase_shift_px: int,
    ) -> np.ndarray:
        """
        Render OOK-modulated horizontal stripes across the LED aperture.

        Each row y inside the LED disc is assigned a bit value from the cyclic
        20-bit packet, based on:
            bit_index = floor((y + phase_shift_px) / pixels_per_bit) % 20

        The LED emits at OOK_HIGH (1.0) for bit=1, OOK_LOW (0.1) for bit=0.
        The intensity is then multiplied by the 2D Gaussian beam profile.

        Returns:
            Float32 BGR array of shape (H, W, 3).
        """
        # Build 20-bit packet as a list of ints
        packet_str = build_packet(node_id)
        packet_bits = [int(b) for b in packet_str]   # list of 20 ints (0 or 1)
        ppb = max(self.pixels_per_bit, 1.0)

        # Circular disc mask
        disc = self._build_circular_disc_mask(led_px_diameter)

        # Build per-row OOK intensity map (shape: H)
        row_indices = np.arange(FRAME_H, dtype=np.float32)
        # Phase shift: shift stripe pattern vertically
        shifted = row_indices + float(phase_shift_px)
        bit_indices = (np.floor(shifted / ppb).astype(np.int32)) % 20
        # Map each row's bit index to OOK level
        ook_levels = np.where(
            np.array(packet_bits)[bit_indices] == 1,
            OOK_HIGH,
            OOK_LOW,
        ).astype(np.float32)   # shape: (H,)

        # Expand to (H, 1) for broadcasting with (H, W) arrays
        ook_row_map = ook_levels[:, np.newaxis]   # (H, 1)

        # Peak brightness for a '1' stripe
        I_peak = 220.0

        # Final per-pixel intensity: Gaussian * OOK * disc * peak
        # gaussian_mask (H,W), disc (H,W), ook_row_map (H,1) -> (H,W)
        intensity = I_peak * gaussian_mask * ook_row_map * disc   # (H, W)

        # Convert to BGR (cool-white LED: B slightly dominant)
        layer = np.zeros((FRAME_H, FRAME_W, 3), dtype=np.float32)
        layer[:, :, 0] = intensity * 1.0    # B
        layer[:, :, 1] = intensity * 0.98   # G
        layer[:, :, 2] = intensity * 0.92   # R (slight blue-white tint)

        return layer

    # ------------------------------------------------------------------
    # Packet info helpers (for overlay telemetry)
    # ------------------------------------------------------------------

    def get_packet_info(self, node_id: int) -> dict:
        """
        Return a dict of packet metadata for HUD overlay use.

        Returns:
            {
              'node_id': int,
              'packet_bits': str (20 chars),
              'preamble': str,
              'node_id_bits': str,
              'crc_bits': str,
              'pixels_per_bit': float,
              'led_freq_hz': float,
              'row_readout_us': float,
            }
        """
        pkt = build_packet(node_id)
        return {
            "node_id": node_id,
            "packet_bits": pkt,
            "preamble": pkt[:8],
            "node_id_bits": pkt[8:16],
            "crc_bits": pkt[16:],
            "pixels_per_bit": self.pixels_per_bit,
            "led_freq_hz": LED_FREQ_HZ,
            "row_readout_us": ROW_READOUT_US,
        }

    def get_led_px_diameter(self, distance_m: float) -> float:
        """Return the projected LED pixel diameter at a given distance."""
        return self._project_diameter(distance_m)
