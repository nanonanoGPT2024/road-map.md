#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi Keamanan Komputer & Kriptografi
Materi: BAB-09 - Keamanan Komputer dan Kriptografi
Fitur:
  1. Hashing Kriptografis & Efek Longsoran (Avalanche Effect)
  2. Symmetric Stream Cipher (Sandi Simetris berbasis PRNG Stream)
  3. Diffie-Hellman Key Exchange (Pertukaran Kunci Asimetris)
  4. Message Authentication Code (HMAC-SHA256) & Deteksi Tampering
"""

import hashlib
import hmac
import os
import secrets
import sys
import time

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"


def print_header(title: str) -> None:
    print(f"\n{BG_BLUE}{WHITE}{BOLD} === [ {title.upper()} ] === {RESET}\n")


def simulate_delay(seconds: float = 0.4) -> None:
    time.sleep(seconds)


# -------------------------------------------------------------
# 1. Hashing & Efek Longsoran (Avalanche Effect)
# -------------------------------------------------------------
def demo_hashing_avalanche() -> None:
    print_header("Modul 1: Hashing & Efek Longsoran (Avalanche Effect)")
    print(f"{CYAN}Prinsip Kriptografi:{RESET} Perubahan 1 bit pada plaintext harus mengubah")
    print(f"sekitar 50% bit output digest secara acak dan deterministik.\n")

    text1 = "SistemKeamananTinggi2026"
    text2 = "SistemKeamananTinggi2027"  # Berubah 1 karakter di akhir

    h1 = hashlib.sha256(text1.encode("utf-8")).digest()
    h2 = hashlib.sha256(text2.encode("utf-8")).digest()

    hex1 = h1.hex()
    hex2 = h2.hex()

    print(f"{YELLOW}Input 1:{RESET} {BOLD}{text1}{RESET}")
    print(f"{GREEN}SHA-256:{RESET} {hex1}")
    print(f"{YELLOW}Input 2:{RESET} {BOLD}{text2}{RESET} (hanya ubah digit terakhir)")
    print(f"{GREEN}SHA-256:{RESET} {hex2}\n")

    # Hitung perbedaan level bit
    diff_bits = 0
    total_bits = len(h1) * 8

    bitstring1 = "".join(f"{byte:08b}" for byte in h1)
    bitstring2 = "".join(f"{byte:08b}" for byte in h2)

    diff_visual = []
    for b1, b2 in zip(bitstring1, bitstring2):
        if b1 != b2:
            diff_bits += 1
            diff_visual.append(f"{RED}{b2}{RESET}")
        else:
            diff_visual.append(f"{DIM}{b2}{RESET}")

    percentage = (diff_bits / total_bits) * 100
    print(f"{WHITE}{BOLD}Analisis Hamming Distance Bit:{RESET}")
    print(f"Visual bit berubah: {''.join(diff_visual[:64])}... (64 bit pertama)")
    print(
        f"Total bit berubah: {BOLD}{diff_bits}/{total_bits} bit ({percentage:.2f}%){RESET}"
    )

    if 40.0 <= percentage <= 60.0:
        print(f"{GREEN}✔ Efek longsoran ideal terpenuhi (~50%).{RESET}")
    else:
        print(f"{YELLOW}⚠ Variasi statistik normal pada sampel pendek.{RESET}")


# -------------------------------------------------------------
# 2. Symmetric Stream Cipher (One-Time Pad / XOR Stream)
# -------------------------------------------------------------
def demo_symmetric_stream() -> None:
    print_header("Modul 2: Enkripsi Simetris (Keystream XOR)")
    print(f"{CYAN}Prinsip:{RESET} Plaintext (P) ⊕ Keystream (K) = Ciphertext (C)")
    print(f"        Ciphertext (C) ⊕ Keystream (K) = Plaintext (P)\n")

    plaintext = "Transaksi Rahasia: Transfer Rp 500.000.000 ke Akun Alpha"
    data_bytes = plaintext.encode("utf-8")

    # Generate kunci acak kriptografis (CSPRNG)
    key = secrets.token_bytes(len(data_bytes))

    # Enkripsi: XOR byte per byte
    ciphertext = bytes([b ^ k for b, k in zip(data_bytes, key)])

    print(f"{WHITE}Plaintext Asli :{RESET} {GREEN}{plaintext}{RESET}")
    print(f"{WHITE}Panjang Data   :{RESET} {len(data_bytes)} byte")
    print(f"{WHITE}Kunci Rahasia  :{RESET} {BLUE}{key.hex()[:32]}... [RAHASIA]{RESET}")
    print(
        f"{WHITE}Ciphertext Hex :{RESET} {MAGENTA}{ciphertext.hex()[:32]}... [TERENKRIPSI]{RESET}\n"
    )

    simulate_delay()

    # Dekripsi
    decrypted_bytes = bytes([c ^ k for c, k in zip(ciphertext, key)])
    decrypted_text = decrypted_bytes.decode("utf-8")

    print(f"{WHITE}Hasil Dekripsi :{RESET} {GREEN}{decrypted_text}{RESET}")
    assert decrypted_text == plaintext, "Gagal memulihkan plaintext!"
    print(f"{GREEN}✔ Verifikasi Integritas Data Simetris Berhasil!{RESET}")


# -------------------------------------------------------------
# 3. Diffie-Hellman Key Exchange Simulation
# -------------------------------------------------------------
def demo_diffie_hellman() -> None:
    print_header("Modul 3: Diffie-Hellman Key Exchange (Kriptografi Asimetris)")
    print(f"{CYAN}Skenario:{RESET} Alice & Bob menyepakati kunci bersama melalui kanal publik")
    print(f"tanpa membocorkan private key masing-masing kepada penguping (Eve).\n")

    # Bilangan prima p dan generator g (ukuran modul edukasi)
    # RFC 3526 MODP 1536-bit disederhanakan untuk eksekusi instan edukasi
    p = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF
    g = 2

    print(f"{WHITE}Parameter Publik:{RESET}")
    print(f"  Generator (g): {g}")
    print(f"  Modulus Prima (p): {hex(p)[:24]}... (1536-bit safe prime)\n")

    # Alice generate private a & public A
    a_priv = secrets.randbelow(p - 2) + 2
    A_pub = pow(g, a_priv, p)

    # Bob generate private b & public B
    b_priv = secrets.randbelow(p - 2) + 2
    B_pub = pow(g, b_priv, p)

    print(
        f"{MAGENTA}[Alice]{RESET} Private: {str(a_priv)[:12]}... | Publik (A = g^a mod p): {hex(A_pub)[:20]}..."
    )
    print(
        f"{BLUE}[Bob]{RESET}   Private: {str(b_priv)[:12]}... | Publik (B = g^b mod p): {hex(B_pub)[:20]}..."
    )
    print(f"{RED}[Eve]{RESET}   Menyadap kanal publik: hanya melihat p, g, A, dan B!")

    simulate_delay()

    # Menghitung shared secret
    # Alice: S = B^a mod p
    # Bob:   S = A^b mod p
    alice_secret = pow(B_pub, a_priv, p)
    bob_secret = pow(A_pub, b_priv, p)

    print(f"\n{YELLOW}Kompilasi Kunci Bersama:{RESET}")
    print(f"  Kunci Alice: {hex(alice_secret)[:32]}...")
    print(f"  Kunci Bob  : {hex(bob_secret)[:32]}...")

    assert (
        alice_secret == bob_secret
    ), "Kunci rahasia bersama Alice dan Bob tidak cocok!"

    # Derivasi AES/Session Key menggunakan SHA-256 dari shared secret
    secret_bytes = alice_secret.to_bytes((alice_secret.bit_length() + 7) // 8, "big")
    session_key = hashlib.sha256(secret_bytes).hexdigest()
    print(
        f"{GREEN}✔ Kunci Rahasia Berhasil Disepakati! Session Key SHA-256: {session_key}{RESET}"
    )


# -------------------------------------------------------------
# 4. HMAC & Deteksi Pemalsuan Data (Tamper Detection)
# -------------------------------------------------------------
def demo_hmac_tampering() -> None:
    print_header("Modul 4: Integritas Pesan & HMAC (Deteksi Pemalsuan)")
    print(f"{CYAN}Prinsip:{RESET} HMAC membuktikan keaslian sumber data (Authentication)")
    print(f"dan memastikan data tidak dimanipulasi di tengah jalan (Integrity).\n")

    secret_key = b"super-secure-distributed-shared-key-2026"
    pesan_asli = b"INSTRUKSI: Transfer dana Rp 10.000.000 ke Vendor A"

    # Buat Tag Otentikasi HMAC-SHA256
    tag_asli = hmac.new(secret_key, pesan_asli, hashlib.sha256).hexdigest()

    print(f"{WHITE}Pesan Asli   :{RESET} {pesan_asli.decode()}")
    print(f"{WHITE}HMAC-SHA256  :{RESET} {GREEN}{tag_asli}{RESET}\n")

    # Skenario 1: Penerima memverifikasi paket yang sah
    valid = hmac.compare_digest(
        tag_asli, hmac.new(secret_key, pesan_asli, hashlib.sha256).hexdigest()
    )
    print(
        f"[Penerima] Verifikasi Paket Asli: {GREEN if valid else RED}{'LOLOS (Sah)' if valid else 'GAGAL'}{RESET}"
    )

    simulate_delay()

    # Skenario 2: Serangan Man-in-the-Middle (MitM Tampering)
    print(f"\n{RED}[Serangan Siber]{RESET} Penyerang mengubah isi pesan di perjalanan...")
    pesan_palsu = (
        b"INSTRUKSI: Transfer dana Rp 99.000.000 ke Rekening Penyerang B"
    )

    tag_verifikasi_palsu = hmac.new(
        secret_key, pesan_palsu, hashlib.sha256
    ).hexdigest()
    valid_tamper = hmac.compare_digest(tag_asli, tag_verifikasi_palsu)

    print(f"{WHITE}Pesan Diterima  :{RESET} {YELLOW}{pesan_palsu.decode()}{RESET}")
    print(f"{WHITE}HMAC Terlampir  :{RESET} {GREEN}{tag_asli}{RESET}")
    print(
        f"{WHITE}HMAC Dihitung   :{RESET} {RED}{tag_verifikasi_palsu}{RESET}"
    )
    print(
        f"[Penerima] Verifikasi Integritas: {RED}{'DITOLAK (Terdeteksi Modifikasi Ilegal!)' if not valid_tamper else 'LOLOS'}{RESET}"
    )


# -------------------------------------------------------------
# Main Interactive / Auto-Runner Menu
# -------------------------------------------------------------
def display_menu() -> None:
    print(f"\n{BOLD}{CYAN}===================================================={RESET}")
    print(f"{BOLD}{WHITE} LAB INTERAKTIF: FONDASI KRIPTOGRAFI & KEAMANAN   {RESET}")
    print(f"{BOLD}{CYAN}===================================================={RESET}")
    print(f"  {YELLOW}1.{RESET} Hashing & Efek Longsoran (Avalanche Effect)")
    print(f"  {YELLOW}2.{RESET} Enkripsi Simetris (Keystream XOR)")
    print(f"  {YELLOW}3.{RESET} Diffie-Hellman Key Exchange (Kunci Publik/Privat)")
    print(f"  {YELLOW}4.{RESET} Integritas Pesan HMAC & Deteksi Modifikasi")
    print(f"  {YELLOW}5.{RESET} Jalankan Seluruh Demonstrasi (Benchmark)")
    print(f"  {YELLOW}0.{RESET} Keluar")
    print(f"{BOLD}{CYAN}----------------------------------------------------{RESET}")


def run_all() -> None:
    demo_hashing_avalanche()
    demo_symmetric_stream()
    demo_diffie_hellman()
    demo_hmac_tampering()
    print(
        f"\n{GREEN}{BOLD}Seluruh simulasi selesai dijalankan dengan status: SUKSES.{RESET}\n"
    )


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "--auto"):
        run_all()
        return

    # Interactive mode default, fallback jika non-TTY
    if not sys.stdin.isatty():
        run_all()
        return

    while True:
        display_menu()
        try:
            choice = input(f"{BOLD}Pilih opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Sesi diakhiri oleh pengguna.{RESET}")
            break

        if choice == "1":
            demo_hashing_avalanche()
        elif choice == "2":
            demo_symmetric_stream()
        elif choice == "3":
            demo_diffie_hellman()
        elif choice == "4":
            demo_hmac_tampering()
        elif choice == "5":
            run_all()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah mempelajari fondasi kriptografi.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")


if __name__ == "__main__":
    main()
