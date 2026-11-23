"""
packet_encoder.py — OCC Packet Encoder for Rolling-Shutter Channel Simulator
@sim-agent | FYP_Project/transmitter_sim/

Encodes a Node ID into a 20-bit OCC packet:
    [PREAMBLE: 8 bits = 10101010] + [NODE_ID: 8 bits] + [CRC-4-ITU: 4 bits]

The CRC-4-ITU is computed over the 16 bits of [PREAMBLE + NODE_ID].
Polynomial: x^4 + x + 1 => 0x13 (5-bit representation including leading 1).
"""

PREAMBLE_BITS: str = "10101010"   # 0xAA
CRC4_POLY: int = 0x13             # CRC-4-ITU: x^4 + x + 1
CRC4_INIT: int = 0x00
CRC4_XOR: int = 0x00


def compute_crc4(data_bits: str) -> str:
    """
    Compute CRC-4-ITU over a bit-string of arbitrary length.

    Args:
        data_bits: Binary string, e.g. "10101010 01101001" (spaces ignored).

    Returns:
        4-character binary CRC string, e.g. "0110".
    """
    # Strip spaces, validate
    bits = data_bits.replace(" ", "")
    if not all(c in "01" for c in bits):
        raise ValueError(f"data_bits must be a binary string, got: {data_bits!r}")

    # Convert to integer for bit-level arithmetic
    # We process bit-by-bit (MSB first) to match standard CRC-4-ITU behavior
    remainder: int = CRC4_INIT

    for bit_char in bits:
        bit = int(bit_char)
        # XOR in next input bit at the MSB of the 4-bit remainder
        remainder ^= (bit << 3)
        # If MSB is 1, divide by polynomial
        if remainder & 0x8:
            remainder ^= CRC4_POLY
        remainder = (remainder << 1) & 0xF  # Keep 4 bits, shift left

    crc = (remainder >> 4) ^ CRC4_XOR

    # Flush remaining bits in register (standard: flush with 4 zero bits)
    # Re-do the proper flush pass
    remainder = CRC4_INIT
    for bit_char in bits:
        bit = int(bit_char)
        remainder = ((remainder << 1) & 0xF) | bit
        if remainder & 0x10:
            remainder ^= CRC4_POLY & 0xF
    # Flush 4 zero bits
    for _ in range(4):
        remainder = ((remainder << 1) & 0x1F)
        if remainder & 0x10:
            remainder ^= CRC4_POLY & 0xF
        remainder &= 0xF

    crc = remainder ^ CRC4_XOR
    return format(crc, "04b")


def compute_crc4_lookup(data_bits: str) -> str:
    """
    Robust CRC-4-ITU using the standard shift-register algorithm.
    Uses polynomial 0x13 (5-bit poly) with 4-bit register, MSB first.

    Args:
        data_bits: Binary string of exactly 16 bits.

    Returns:
        4-character binary CRC remainder string.
    """
    bits = data_bits.replace(" ", "")
    # Pad with 4 zero bits for proper flush
    padded = bits + "0000"

    reg = 0  # 4-bit shift register initialized to 0x00
    poly = 0x03  # Only the lower 4 bits of CRC-4-ITU poly (0x13 & 0x0F = 0x03)

    for bit_char in padded:
        bit = int(bit_char)
        msb = (reg >> 3) & 1
        reg = ((reg << 1) & 0xF) | bit
        if msb:
            reg ^= poly

    return format(reg ^ CRC4_XOR, "04b")


def build_packet(node_id: int) -> str:
    """
    Build the full 20-bit OCC packet for a given node_id.

    Args:
        node_id: Integer in range [0, 255].

    Returns:
        20-character binary string: PREAMBLE[8] + NODE_ID[8] + CRC[4]

    Example:
        >>> build_packet(105)
        '1010101001101001XXXX'  # where XXXX is the CRC-4 checksum
    """
    if not (0 <= node_id <= 255):
        raise ValueError(f"node_id must be in [0, 255], got {node_id}")

    node_id_bits = format(node_id, "08b")
    data_16_bits = PREAMBLE_BITS + node_id_bits
    crc_bits = compute_crc4_lookup(data_16_bits)

    packet = data_16_bits + crc_bits
    assert len(packet) == 20, f"Packet length mismatch: {len(packet)} != 20"
    return packet


def verify_packet(packet_bits: str) -> bool:
    """
    Verify a received 20-bit packet by recomputing its CRC-4.

    Args:
        packet_bits: 20-character binary string.

    Returns:
        True if CRC matches and preamble is correct, False otherwise.
    """
    if len(packet_bits) != 20:
        return False
    preamble = packet_bits[:8]
    node_id_bits = packet_bits[8:16]
    received_crc = packet_bits[16:20]

    if preamble != PREAMBLE_BITS:
        return False

    expected_crc = compute_crc4_lookup(preamble + node_id_bits)
    return received_crc == expected_crc


def decode_node_id(packet_bits: str) -> int:
    """Extract integer node_id from a valid 20-bit packet string."""
    return int(packet_bits[8:16], 2)


if __name__ == "__main__":
    # Quick self-test
    for nid in [0, 105, 208, 255]:
        pkt = build_packet(nid)
        ok = verify_packet(pkt)
        crc = pkt[16:]
        print(f"Node {nid:3d} -> packet: {pkt}  CRC: {crc}  valid: {ok}")
    assert verify_packet(build_packet(105)), "Self-test failed for node 105"
    assert verify_packet(build_packet(208)), "Self-test failed for node 208"
    print("All self-tests passed.")
