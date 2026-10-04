#!/usr/bin/env python3
"""
IPsec IKEv2 Handshake & Stateful Packet Inspection (SPI) Firewall Simulator
---------------------------------------------------------------------------
Simulasi komprehensif tingkat kernel/network engine yang merepresentasikan:
1. Negosiasi Kriptografi IKEv2 (IKE_SA_INIT & IKE_AUTH) menggunakan Diffie-Hellman & HMAC.
2. Enkapsulasi Paket ESP (Encapsulating Security Payload) dengan Seq Number, Padding, dan ICV.
3. Stateful Packet Inspection (SPI) Engine dengan Connection Tracking (Conntrack) Table.
4. Pengujian Asymmetric Flow & Penolakan Paket Injeksi Tanpa State Valid.

Kebutuhan: Python 3.8+ (Hanya menggunakan pustaka standar Python)
"""

import hashlib
import hmac
import os
import struct
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Optional, Tuple


# ==============================================================================
# 1. KRIPTOGRAFI SEDERHANA & PROTOKOL IKEv2
# ==============================================================================

class DHGroup19Simulator:
    """
    Simulasi matematis Diffie-Hellman Key Exchange (RFC 5903 Curve25519/Group 19 concept).
    Menghasilkan shared secret yang identik di kedua sisi tunnel.
    """
    def __init__(self):
        # Menggunakan bilangan prima besar dan generator untuk simulasi pertukaran DH
        self.prime = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
        self.generator = 2
        self._private_key = int.from_bytes(os.urandom(32), byteorder="big") % self.prime

    def get_public_key(self) -> int:
        return pow(self.generator, self._private_key, self.prime)

    def compute_shared_secret(self, peer_public_key: int) -> bytes:
        shared_int = pow(peer_public_key, self._private_key, self.prime)
        return shared_int.to_bytes(32, byteorder="big")


@dataclass
class IKEv2SecurityAssociation:
    initiator_spi: bytes
    responder_spi: bytes
    shared_key: bytes
    sk_enc: bytes  # Encryption key
    sk_int: bytes  # Integrity key
    seq_counter: int = 0


def derive_ipsec_keys(shared_secret: bytes, nonces: bytes) -> Tuple[bytes, bytes]:
    """Derivasi material kunci SKEYSEED -> SK_enc & SK_int menggunakan PRF (HMAC-SHA256)."""
    skeyseed = hmac.new(nonces, shared_secret, hashlib.sha256).digest()
    sk_enc = hmac.new(skeyseed, b"ENC_KEY_DERIVATION_PAYLOAD", hashlib.sha256).digest()
    sk_int = hmac.new(skeyseed, b"INT_KEY_DERIVATION_PAYLOAD", hashlib.sha256).digest()
    return sk_enc, sk_int


# ==============================================================================
# 2. ENKAPSULASI ESP (ENCAPSULATING SECURITY PAYLOAD)
# ==============================================================================

@dataclass
class ESPPacket:
    spi: int
    seq_no: int
    iv: bytes
    encrypted_payload: bytes
    padding: bytes
    next_header: int
    icv: bytes  # Integrity Check Value

    def serialize(self) -> bytes:
        esp_header = struct.pack("!II", self.spi, self.seq_no)
        trailer = self.padding + bytes([len(self.padding), self.next_header])
        raw = esp_header + self.iv + self.encrypted_payload + trailer
        return raw + self.icv


def encrypt_esp_payload(payload: bytes, sa: IKEv2SecurityAssociation, next_header: int = 6) -> ESPPacket:
    """Membungkus paket L4 ke dalam format ESP Tunnel Mode."""
    sa.seq_counter += 1
    iv = os.urandom(16)
    
    # Kalkulasi XOR Stream cipher sederhana berbasis SK_enc + IV (Simulasi AES-CTR)
    keystream = hashlib.sha256(sa.sk_enc + iv).digest()
    while len(keystream) < len(payload):
        keystream += hashlib.sha256(sa.sk_enc + keystream).digest()
    encrypted_data = bytes(p ^ k for p, k in zip(payload, keystream[:len(payload)]))

    # ESP 32-bit alignment padding
    pad_len = (4 - ((len(payload) + 2) % 4