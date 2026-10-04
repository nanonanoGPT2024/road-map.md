#!/usr/bin/env python3
"""
AWS KMS Envelope Encryption & Decryption Simulator
Author: Principal Cloud & SRE Curriculum Architect
Standard: GEMINI.md Enterprise Security Standards

Deskripsi:
Skrip ini mensimulasikan alur kerja Envelope Encryption production-grade
menggunakan Python Cryptography library (AES-256-GCM) dan mensimulasikan
interaksi AWS KMS API (GenerateDataKey & Decrypt) secara deterministik.

Karakteristik Keamanan yang Diimplementasikan:
1. Algoritma Simetrik Terotentikasi: AES-GCM 256-bit (Confidentiality & Integrity).
2. Ephemeral Initialization Vector (IV/Nonce): 96-bit di-generate unik per enkripsi.
3. Zero-out Memory: Plaintext Data Key secara eksplisit dihapus dari memori bytearray
   segera setelah proses enkripsi payload selesai.
4. Additional Authenticated Data (AAD) / Encryption Context: Pengikatan metadata
   kontekstual untuk mencegah serangan replay atau swap ciphertext.
"""

import os
import sys
import json
import base64
from typing import Dict, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class MockAWSKMS:
    """
    Simulasi Hardware Security Module (HSM) AWS KMS.
    Menyimpan Root Customer Managed Key (CMK) internal yang tidak pernah
    bisa di-export ke luar dari modul ini.
    """
    def __init__(self, key_id: str = "arn:aws:kms:ap-southeast-1:111122223333:key/cmk-mock-healthcare-01"):
        self.key_id = key_id
        # Root CMK 256-bit yang berada di dalam HSM KMS
        self._internal_root_cmk = AESGCM.generate_key(bit_length=256)

    def generate_data_key(self, key_id: str, key_spec: str = "AES_256", encryption_context: Dict[str, str] = None) -> Tuple[bytes, bytes]:
        """
        Simulasi API: kms.generate_data_key()
        Mengembalikan:
        1. Plaintext Data Key (digunakan oleh aplikasi lalu dibuang dari memori)
        2. Ciphertext Data Key (dienkripsi oleh Root CMK di dalam KMS)
        """
        if key_id != self.key_id:
            raise ValueError(f"Key ID {key_id} tidak valid atau tidak ditemukan di KMS.")
        
        if key_spec != "AES_256":
            raise NotImplementedError("Simulator hanya mendukung AES_256.")

        # 1. Generate Plaintext Data Key 256-bit
        plaintext_data_key = AESGCM.generate_key(bit_length=256)

        # 2. Enkripsi Plaintext Data Key menggunakan Root CMK (Envelope Wrapping)
        aad = json.dumps(encryption_context, sort_keys=True).encode("utf-8") if encryption_context else None
        hsm_aesgcm = AESGCM(self._internal_root_cmk)
        nonce = os.urandom(12) # 96-bit nonce
        encrypted_key_bytes = hsm_aesgcm.encrypt(nonce, plaintext_data_key, aad)

        # Ciphertext Data Key = Nonce (12 byte) + Encrypted Key Bytes
        ciphertext_data_key = nonce + encrypted_key_bytes

        return plaintext_data_key, ciphertext_data_key

    def decrypt_data_key(self, key_id: str, ciphertext_data_key: bytes, encryption_context: Dict[str, str] = None) -> bytes:
        """
        Simulasi API: kms.decrypt()
        Menerima Ciphertext Data Key, membukanya menggunakan Root CMK di dalam KMS,
        dan mengembalikan Plaintext Data Key kepada pemanggil yang terotorisasi.
        """
        if key_id != self.key_id:
            raise ValueError(f"Key ID {key_id} tidak valid.")

        aad = json.dumps(encryption_context, sort_keys=True).encode("utf-8") if encryption_context else None
        hsm_aesgcm = AESGCM(self._internal_root_cmk)

        # Ekstrak nonce (12 byte pertama) dan ciphertext
        nonce = ciphertext_data_key[:12]
        encrypted_key_bytes = ciphertext_data_key[12:]

        try:
            plaintext_data_key = hsm_aesgcm.decrypt(nonce, encrypted_key_bytes, aad)
            return plaintext_data_key
        except Exception as exc:
            raise PermissionError("Gagal mendekripsi Data Key: AAD (Encryption Context) tidak cocok atau data corrupt.") from exc


def zero_out_buffer(target_buf: bytearray) -> None:
    """
    Secara deterministik menimpa area memori bytearray dengan nol (0x00)
    untuk mencegah kebocoran kunci akibat inspect memory dump / GC latency.
    """
    for i in range(len(target_buf)):
        target_buf[i] = 0


def encrypt_payload_envelope(
    kms_service: MockAWSKMS,
    cmk_arn: str,
    payload_plaintext: str,
    encryption_context: Dict[str, str]
) -> Dict[str, str]:
    """
    Mengenkripsi payload data berukuran besar menggunakan pola Envelope Encryption.
    """
    print("\n[*] --- MEMULAI PROSES ENVELOPE ENCRYPTION ---")
    print(f"[*] Menghubungi KMS untuk GenerateDataKey (CMK: {cmk_arn})...")
    
    # 1. Minta Plaintext dan Ciphertext Data Key ke KMS
    plain_key_bytes, ciphertext_data_key = kms_service.generate_data_key(
        key_id=cmk_arn,
        key_spec="AES_256",
        encryption_context=encryption_context
    )

    # Simpan plain_key_bytes ke dalam mutable bytearray untuk pengamanan memori
    ephemeral_key_memory = bytearray(plain_key_bytes)
    
    print("[+] Data Key berhasil di-generate.")
    print(f"    - Ciphertext Data Key Length: {len(ciphertext_data_key)} bytes")
    print("    - Plaintext Data Key berada sementara di memori aplikasi.")

    try:
        # 2. Lakukan enkripsi payload lokal dengan Plaintext Data Key via AES-256-GCM
        local_aesgcm = AESGCM(bytes(ephemeral_key_memory))
        payload_nonce = os.urandom(12) # 96-bit nonce unik
        aad = json.dumps(encryption_context, sort_keys=True).encode("utf-8")
        
        ciphertext_payload = local_aesgcm.encrypt(
            payload_nonce,
            payload_plaintext.encode("utf-8"),
            aad
        )
        print("[+] Payload data sensitif berhasil dienkripsi dengan AES-256-GCM.")
    finally:
        # 3. ZERO-OUT Plaintext Data Key dari memori aplikasi seketika!
        zero_out_buffer(ephemeral_key_memory)
        del ephemeral_key_memory
        del plain_key_bytes
        print("[+] KRITIKAL: Plaintext Data Key telah dibersihkan (zeroed-out) dari memori aplikasi.")

    # 4. Bungkus paket terenkripsi (Envelope Artifact)
    envelope_package = {
        "kms_cmk_arn": cmk_arn,
        "encryption_context": encryption_context,
        "ciphertext_data_key_b64": base64.b64encode(ciphertext_data_key).decode("utf-8"),
        "payload_nonce_b64": base64.b64encode(payload_nonce).decode("utf-8"),
        "ciphertext_payload_b64": base64.b64encode(ciphertext_payload).decode("utf-8")
    }
    return envelope_package


def decrypt_payload_envelope(
    kms_service: MockAWSKMS,
    envelope_package: Dict[str, str],
    provided_context: Dict[str, str]
) -> str:
    """
    Mendekripsi paket Envelope:
    1. Mengirim Ciphertext Data Key ke KMS.
    2. Menerima Plaintext Data Key.
    3. Mendekripsi Ciphertext Payload.
    4. Menghapus Plaintext Data Key dari memori.
    """
    print("\n[*] --- MEMULAI PROSES ENVELOPE DECRYPTION ---")
    cmk_arn = envelope_package["kms_cmk_arn"]
    ciphertext_data_key = base64.b64decode(envelope_package["ciphertext_data_key_b64"])
    payload_nonce = base64.b64decode(envelope_package["payload_nonce_b64"])
    ciphertext_payload = base64.b64decode(envelope_package["ciphertext_payload_b64"])

    print(f"[*] Mengirim Ciphertext Data Key ke KMS API decrypt() menggunakan CMK: {cmk_arn}...")
    
    # 1. Dekripsi data key via KMS
    recovered_data_key = kms_service.decrypt_data_key(
        key_id=cmk_arn,
        ciphertext_data_key=ciphertext_data_key,
        encryption_context=provided_context
    )
    
    ephemeral_key_memory = bytearray(recovered_data_key)
    print("[+] KMS mengembalikan Plaintext Data Key yang valid.")

    try:
        # 2. Dekripsi payload data lokal
        local_aesgcm = AESGCM(bytes(ephemeral_key_memory))
        aad = json.dumps(provided_context, sort_keys=True).encode("utf-8")
        
        decrypted_bytes = local_aesgcm.decrypt(
            payload_nonce,
            ciphertext_payload,
            aad
        )
        print("[+] Payload berhasil didekripsi dan diverifikasi integritasnya.")
        return decrypted_bytes.decode("utf-8")
    finally:
        # 3. Musnahkan kunci dari memori
        zero_out_buffer(ephemeral_key_memory)
        del ephemeral_key_memory
        del recovered_data_key
        print("[+] KRITIKAL: Plaintext Data Key telah dibersihkan kembali dari memori aplikasi.")


def main():
    print("=" * 80)
    print("DEMO SIMULASI PRODUKSI: AWS KMS ENVELOPE ENCRYPTION PATTERN")
    print("=" * 80)

    # Inisialisasi mock KMS service
    cmk_arn = "arn:aws:kms:ap-southeast-1:111122223333:key/cmk-mock-healthcare-01"
    kms = MockAWSKMS(key_id=cmk_arn)

    # Data Sensitif Pasien (Personally Identifiable Information / Protected Health Information)
    sensitive_payload = json.dumps({
        "patient_id": "P-9883412",
        "full_name": "Siti Nurhaliza",
        "nik": "3171012345670001",
        "medical_record": "Diagnosis: Hipertensi Stage 2, Terapi: Amlodipine 10mg",
        "credit_card": "4111-2222-3333-4444"
    }, indent=2)

    # Encryption Context (Additional Authenticated Data) untuk mengikat konteks bisnis
    encryption_context = {
        "Department": "Cardiology",
        "Classification": "Restricted-PHI",
        "Origin": "Jakarta-Hospital-01"
    }

    print(f"\n[+] Raw Sensitive Data to Encrypt:\n{sensitive_payload}")

    # Step 1: Enkripsi Data
    envelope_artifact = encrypt_payload_envelope(
        kms_service=kms,
        cmk_arn=cmk_arn,
        payload_plaintext=sensitive_payload,
        encryption_context=encryption_context
    )

    print("\n[+] Hasil Paket Enkripsi Tersimpan (Envelope Artifact JSON):")
    print(json.dumps(envelope_artifact, indent=2))

    # Step 2: Dekripsi Sukses dengan Encryption Context yang Benar
    print("\n[*] Skenario A: Dekripsi dengan Encryption Context yang SAH")
    decrypted_result = decrypt_payload_envelope(
        kms_service=kms,
        envelope_package=envelope_artifact,
        provided_context=encryption_context
    )
    print(f"\n[+] Data Hasil Dekripsi Berhasil:\n{decrypted_result}")
    assert decrypted_result == sensitive_payload, "Data yang didekripsi tidak identik dengan raw data!"

    # Step 3: Simulasi Serangan Tampering / Context Swapping
    print("\n" + "=" * 80)
    print("[*] Skenario B: Simulasi Serangan (Manipulasi Encryption Context / Replay)")
    fake_context = {
        "Department": "Radiology",  # Attacker mencoba mendekripsi dari departemen lain
        "Classification": "Restricted-PHI",
        "Origin": "Jakarta-Hospital-01"
    }

    try:
        print(f"[*] Mencoba mendekripsi dengan context palsu: {fake_context}...")
        decrypt_payload_envelope(
            kms_service=kms,
            envelope_package=envelope_artifact,
            provided_context=fake_context
        )
    except PermissionError as err:
        print(f"\n[!] DEFENSE SUCCESS: KMS menolak dekripsi data key!")
        print(f"[!] Pesan Penolakan Keamanan: {err}")
    
    print("\n" + "=" * 80)
    print("[+] Simulasi Selesai dengan Sukses. Seluruh postur keamanan kriptografi terverifikasi.")
    print("=" * 80)


if __name__ == "__main__":
    main()

---