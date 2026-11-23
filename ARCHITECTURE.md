# Rolling Shutter OCC Framework — Architecture & Protocol Contract

## 1. System Overview

```
+-----------------------------------------------------------------------------------------+
|                                TRANSMITTER SUBSYSTEM                                    |
| [Preamble: 10101010] + [Node ID: 8 bits] ---> [CRC-4] ---> 20-bit Packet                |
| High-Frequency OOK LED Driver (f_mod = 10 kHz)                                          |
+-----------------------------------------------------------------------------------------+
                                           |
                                  Optical Free Space
                       (Distance d, Path Loss, Ambient Noise, Headlights)
                                           v
+-----------------------------------------------------------------------------------------+
|                                 CMOS CAMERA SENSOR                                      |
| Rolling Shutter Temporal-to-Spatial Scanning: t_row = y * t_readout                      |
| Result: Alternating Bright & Dark Horizontal Stripes across 1920x1080 Frame             |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                             RECEIVER DEMODULATION PIPELINE                              |
| Stage 1: RoI Extraction & Transmitter Localization (Thresholding + Contours)            |
| Stage 2: 2D-to-1D Waveform Extraction (Cross-row Horizontal Pixel Averaging)            |
| Stage 3: Baseline Correction & Binarization (Moving Average Detrending + Dyn. Thresh)   |
| Stage 4: Stripe Width Decoding, Preamble Sync (10101010), Node ID & CRC Validation      |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                4-QUADRANT VISUAL HUD                                    |
| Q1: Full Frame + Tracked Bounding Box  | Q2: Cropped Modulated LED RoI                  |
| Q3: Waveform & Binarization Plot       | Q4: Telemetry (Node ID, CRC, Distance, FPS)   |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Shared Packet Protocol Specification

The transmission packet consists of **20 bits** formatted strictly as follows:

| Bit Range | Field Name | Width (Bits) | Value / Format | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Bits 0–7** | `PREAMBLE` | 8 bits | `10101010` (`0xAA`) | Frame synchronization & symbol clock extraction |
| **Bits 8–15** | `NODE_ID` | 8 bits | `0x00` – `0xFF` (0–255) | Unique Streetlight Infrastructure ID |
| **Bits 16–19**| `CRC_4` | 4 bits | CRC-4-ITU over Bits 0–15 | Error detection & bit-flip validation |

### CRC-4 Calculation Standard
- **Polynomial:** $P(x) = x^4 + x + 1$ (Binary: `10011`, hex: `0x13`).
- **Initial Remainder:** `0x00`
- **Final XOR:** `0x00`
- **Input Data:** 16 bits (`[PREAMBLE (8)] + [NODE_ID (8)]`).

---

## 3. Optical Physics & Rolling Shutter Imaging Contract

### 3.1 Pinhole Camera Geometry & Distance Scaling
Given camera focal length $f$ (mm), real-world LED diameter $D_{real}$ (meters), and distance $d$ (meters):
$$h_{px} = \frac{f \cdot D_{real}}{d \cdot p_{size}}$$
where $p_{size}$ is the camera sensor pixel pitch (meters/pixel).
- Distance estimation formula:
$$\hat{d} = \frac{f \cdot D_{real}}{h_{px} \cdot p_{size}}$$

### 3.2 Rolling Shutter Temporal-to-Spatial Conversion
Each row $y$ ($0 \le y < H_{frame}$) is exposed at time offset:
$$t(y) = t_0 + y \cdot t_{row}$$
where $t_{row}$ is the line readout time ($\approx 29.6\ \mu\text{s}$ for 1080p @ 30fps).
The physical stripe height for one modulated symbol bit of duration $T_b = \frac{1}{f_{mod}}$ is:
$$w_{stripe} = \frac{T_b}{t_{row}} = \frac{1}{f_{mod} \cdot t_{row}} \text{ pixels}$$

### 3.3 Spatial Intensity Profile
The received pixel intensity across the transmitter region combines Gaussian beam spatial falloff and OOK temporal modulation:
$$I(x, y) = \Big[ I_0 \cdot \exp\Big(-\frac{(x - x_c)^2 + (y - y_c)^2}{2\sigma_r^2}\Big) \Big] \cdot M(t(y)) + I_{ambient} + \mathcal{N}(0, \sigma_n^2)$$
where $M(t(y)) \in \{0.1, 1.0\}$ represents the low/high LED emission states.

---

## 4. 4-Stage Computer Vision Demodulation Pipeline

### Stage 1: RoI Extraction & Transmitter Localization
1. Convert frame to Grayscale.
2. Apply adaptive / Otsu thresholding or high-intensity bandpass filtering:
   $$B(x, y) = \begin{cases} 255 & \text{if } I(x, y) \ge T_{roi} \\ 0 & \text{otherwise} \end{cases}$$
3. Perform morphological dilation and contour detection to extract the bounding box $[x, y, W, H]$ of the streetlight LED.

### Stage 2: 2D-to-1D Spatial Waveform Extraction
Collapse horizontal spatial rows into a single 1D temporal-equivalent signal by computing the row-wise mean:
$$S(y) = \frac{1}{W} \sum_{x=0}^{W-1} I_{RoI}(x, y) \quad \text{for } y \in [0, H-1]$$
This significantly suppresses sensor shot noise and random horizontal aberrations.

### Stage 3: Baseline Correction & Adaptive Binarization
1. Estimate low-frequency Gaussian beam curvature baseline $B(y)$ using moving average or Savitzky-Golay / polynomial fit:
   $$B(y) = \frac{1}{2K+1}\sum_{k=-K}^{K} S(y+k)$$
2. Compute detrended waveform:
   $$\tilde{S}(y) = S(y) - B(y)$$
3. Perform zero-crossing or dynamic threshold binarization:
   $$D(y) = \begin{cases} 1 & \text{if } \tilde{S}(y) \ge 0 \\ 0 & \text{otherwise} \end{cases}$$

### Stage 4: Stripe Width Estimation, Preamble Sync & Bit Recovery
1. Measure run-lengths of consecutive 1s and 0s to determine estimated single stripe width $\hat{w}_{stripe}$.
2. Scan the binarized signal for the 8-bit synchronization preamble pattern `10101010`.
3. Sample the signal at intervals of $\hat{w}_{stripe}$ starting from the synchronized preamble offset.
4. Extract the subsequent 8 bits (`NODE_ID`) and 4 bits (`CRC_4`).
5. Recompute CRC-4 over the received payload and validate integrity (`CRC_PASS` / `CRC_FAIL`).
