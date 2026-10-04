## SEKSI 01 — IDENTITAS MODUL

*   **Kurikulum:** Computer Science
*   **Kategori:** 01-Core-Foundations
*   **Bab:** 09 — Keamanan Komputer & Kriptografi
*   **Modul:** 01 — Fondasi Kriptografi: Primitif Kriptografi, Model Ancaman, Enkripsi Simetris/Asimetris, dan Integritas Data
*   **Tingkat Kesulitan:** Intermediate / Advanced
*   **Prasyarat Konseptual:** Matematika Diskrit (Teori Bilangan, Aritmetika Modular, Aljabar Boolean), Struktur Data & Algoritma, Arsitektur Sistem Komputer.
*   **Alokasi Waktu:** 8 Jam Teori, 12 Jam Praktik Laboratorium.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis Ancaman Keamanan (Evaluating - C5):** Memetakan model ancaman (*threat modeling*) terhadap suatu sistem komputasi menggunakan paradigma CIA Triad (Confidentiality, Integrity, Availability) dan DAD Triad (Disclosure, Alteration, Denial).
2.  **Menguraikan Primitif Kriptografi Simetris (Analyzing - C4):** Menjelaskan mekanika internal *block cipher* (struktur SPN dan Feistel Network), mode operasi (*block cipher modes* seperti CBC, CTR, GCM), serta bahaya matematis penggunaan *Initial Vector* (IV) yang deterministik.
3.  **Mengimplementasikan Kriptografi Asimetris (Applying - C3):** Merekonstruksi algoritma pertukaran kunci Diffie-Hellman dan kriptosistem RSA/ECC berdasarkan komputasi modular dan masalah logaritma diskret.
4.  **Memvalidasi Integritas dan Otentisitas Data (Evaluating - C5):** Mengidentifikasi perbedaan kritis antara *error-detection code* (CRC32), fungsi *cryptographic hash* (SHA-256, SHA-3), *Hash-based Message Authentication Code* (HMAC), dan Tanda Tangan Digital (*Digital Signatures*).
5.  **Membangun Sistem Enkripsi Terotentikasi Hibrida (Creating - C6):** Merancang skema *Authenticated Encryption with Associated Data* (AEAD) berbasis AES-256-GCM yang digabungkan dengan mekanisme enkripsi kunci publik untuk transmisi data end-to-end yang aman dari serangan *chosen-ciphertext attack* (CCA).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            KEAMANAN KOMPUTER
                                    │
               ┌────────────────────┴────────────────────┐
               ▼                                         ▼
       MODEL KEAMANAN                            PRIMITIF KRIPTOGRAFI
    (CIA / Threat Model)                                 │
               │                   ┌─────────────────────┼─────────────────────┐
               ▼                   ▼                     ▼                     ▼
    ┌──────────────────────┐  SIMETRIS               ASIMETRIS            INTEGRITAS & OTENTIKASI
    │ Confidentiality      │  (Shared Secret)        (Public/Private)     (Data & Origin)
    │ Integrity            │       │                     │                     │
    │ Availability         │       ├─ Block Cipher       ├─ RSA (Faktorisasi)  ├─ Cryptographic Hash
    │ Authenticity         │       │  ├─ SPN (AES)       ├─ ECC (ECDH/ECDSA)   │  ├─ SHA-256 / SHA-3
    │ Non-repudiation      │       │  └─ Feistel (DES)   └─ Post-Quantum       │  └─ Avalanche Effect
    └──────────────────────┘       ├─ Modes of Op           (Lattice-based)    ├─ MAC / HMAC
                                   │  ├─ ECB (Insecure)                        └─ Digital Signatures
                                   │  ├─ CBC / CTR
                                   │  └─ GCM (AEAD)
                                   └─ Stream Cipher
                                      └─ ChaCha20
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Kriptografi bukan sekadar fungsionalitas tambahan dalam rekayasa perangkat lunak; ia adalah benteng matematis terakhir yang melindungi integritas informasi di atas infrastruktur jaringan fisik yang pada dasarnya *untrusted* (tidak tepercaya). 

1.  **Dunia yang Rentan Secara Default:** Protokol internet dirancang tanpa lapisan autentikasi intrinsik. Paket IP dapat dipalsukan (*spoofing*), kabel fiber optik dapat disadap (*wiretapping*), dan memori perute (*router*) dapat dimanipulasi (*man-in-the-middle*). Tanpa kriptografi, seluruh transaksi perbankan, integritas basis data, dan privasi personal runtuh.
2.  **Konsekuensi Katastropik:** Kesalahan desain primitif atau kesalahan implementasi keamanan (seperti kebocoran *nonce*, penggunaan mode ECB, atau kerentanan saluran samping/*side-channel attack*) berakibat fatal: pencurian aset kripto bernilai jutaan dolar, kompromi infrastruktur nasional kritis, dan eksposur rahasia negara.
3.  **Kebutuhan Engineering Nyata:** Pengembang perangkat lunak modern tidak boleh menganggap fungsi kriptografi sebagai kotak hitam (*black box*). Pemahaman mendalam mengenai limitasi matematis, *padding oracle*, *replay attack*, dan degradasi entropi wajib dimiliki untuk memilih algoritma, panjang kunci, dan konfigurasi yang tepat dalam mengamankan sistem terdistribusi skala besar.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Model Keamanan Inti
*   **CIA Triad:**
    *   **Confidentiality (Kerahasiaan):** Pencegahan akses data oleh entitas yang tidak terotorisasi. Diimplementasikan via enkripsi.
    *   **Integrity (Integritas):** Jaminan bahwa data belum diubah, dimanipulasi, atau disisipi secara ilegal selama transmisi atau penyimpanan. Diimplementasikan via fungsi *hash* kriptografis dan MAC.
    *   **Availability (Ketersediaan):** Jaminan aksesibilitas sistem dan data secara reliabel saat dibutuhkan oleh entitas terotorisasi. Dilindungi via mitigasi DoS/DDoS, redundansi, dan arsitektur *fault-tolerant*.
*   **Authenticity & Non-repudiation:** Jaminan validitas identitas pengirim dan ketidakmampuan pengirim untuk menyangkal keabsahan pesan yang dibuatnya.

### 2. Prinsip Kerckhoffs & Shannon
*   **Prinsip Kerckhoffs:** Keamanan suatu sistem kriptografi tidak boleh bergantung pada kerahasiaan algoritma (*security through obscurity*), melainkan secara eksklusif bergantung pada kerahasiaan kunci (*key*). Algoritma harus dipublikasikan secara terbuka untuk diuji secara matematis dan kriptoanalisis publik.
*   **Shannon's Perfect Secrecy:** Dicapai hanya jika $P(M = m | C = c) = P(M = m)$. Ini menyatakan bahwa *ciphertext* tidak memberikan informasi apa pun mengenai *plaintext*. Satu-satunya skema praktis yang memenuhi kondisi ini adalah **One-Time Pad (OTP)** dengan syarat kunci berukuran $\ge$ pesan, benar-benar acak (*true random*), dan tidak pernah digunakan ulang.

### 3. Enkripsi Simetris
Menggunakan satu kunci rahasia bersama ($K$) untuk proses enkripsi ($E$) dan dekripsi ($D$):
$$C = E_K(M) \quad \text{dan} \quad M = D_K(C)$$
*   **Block Cipher:** Memproses data dalam blok berukuran tetap (misal: 128 bit). Menggunakan jaringan substitusi-permutasi (*Substitution-Permutation Network* / SPN) atau *Feistel Network*.
*   **Stream Cipher:** Menghasilkan deret bit semu-acak (*keystream*) yang dioperasikan secara XOR terhadap *plaintext* bit-demi-bit (misal: ChaCha20).

### 4. Enkripsi Asimetris (Public-Key Cryptography)
Menggunakan pasangan kunci yang terikat secara matematis: Kunci Publik ($K_{pub}$) untuk enkripsi/verifikasi dan Kunci Privat ($K_{priv}$) untuk dekripsi/penandatanganan:
$$C = E_{K_{pub}}(M) \quad \text{dan} \quad M = D_{K_{priv}}(C)$$
Keamanan asimetris didasarkan pada masalah matematika yang sulit diselesaikan dalam waktu polinomial (*trapdoor one-way functions*):
*   Faktorisasi Bilangan Bulat Besar (RSA)
*   Discrete Logarithm Problem (Diffie-Hellman, DSA)
*   Elliptic Curve Discrete Logarithm Problem (ECDH, ECDSA, Ed25519)

### 5. Fungsi Hash Kriptografis & MAC
Fungsi satu arah $H(M)$ yang memetakan input sembarang panjang menjadi output berukuran tetap (*digest*). Harus memenuhi tiga properti utama:
1.  **Pre-image Resistance (One-Way):** Diberikan $h$, secara komputasi mustahil menemukan $m$ sedemikian sehingga $H(m) = h$.
2.  **Second Pre-image Resistance (Weak Collision Resistance):** Diberikan $m_1$, secara komputasi mustahil menemukan $m_2 \neq m_1$ sedemikian sehingga $H(m_1) = H(m_2)$.
3.  **Collision Resistance (Strong Collision Resistance):** Secara komputasi mustahil menemukan pasangan sembarang $(m_1, m_2)$ dengan $m_1 \neq m_2$ sedemikian sehingga $H(m_1) = H(m_2)$. Sesuai fenomena *Birthday Paradox*, resistensi tabrakan untuk *hash* berukuran $n$-bit adalah $2^{n/2}$.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Struktur Algoritma Enkripsi Simetris: SPN (Advanced Encryption Standard - AES)
AES beroperasi pada representasi *state array* $4 \times 4$ *byte* (128-bit). Bergantung pada ukuran kunci (128, 192, atau 256 bit), jumlah putaran (*rounds*) bervariasi ($N_r = 10, 12, \text{atau } 14$). Setiap putaran standar terdiri dari 4 transformasi aljabar:
1.  **SubBytes:** Substitusi non-linear menggunakan *S-Box* yang dibentuk dari inversi multiplikatif dalam medan Galois $GF(2^8)$ diikuti oleh transformasi afin. Memberikan sifat *Confusion* (Shannon).
2.  **ShiftRows:** Permutasi siklik linear terhadap baris-baris *state*. Baris $i$ digeser ke kiri sejauh $i$ byte secara siklik. Memberikan sifat *Diffusion*.
3.  **MixColumns:** Transformasi linear yang memperlakukan setiap kolom sebagai polinomial atas $GF(2^8)$ dan mengalikannya dengan modulo $x^4 + 1$ terhadap matriks konstan.
4.  **AddRoundKey:** Operasi bitwise XOR antara *state* saat ini dengan subkunci putaran (*round key*) yang dihasilkan oleh algoritma *Key Schedule*.

```
Input Plaintext (16 bytes)
        │
        ▼
  [AddRoundKey]  ◄── (Round Key 0)
        │
┌───────┴───────────────────────────────────────┐
│ Loop Rounds 1 hingga (Nr - 1):                │
│   1. [SubBytes]    (S-Box Nonlinearity)       │
│   2. [ShiftRows]   (Permutasi Baris)          │
│   3. [MixColumns]  (Difusi Kolom GF(2^8))     │
│   4. [AddRoundKey] (XOR Round Key i)          │
└───────┬───────────────────────────────────────┘
        │
   (Final Round - Tanpa MixColumns):
    1. [SubBytes]
    2. [ShiftRows]
    3. [AddRoundKey] ◄── (Round Key Nr)
        │
        ▼
 Output Ciphertext (16 bytes)
```

### 2. Mode Operasi Block Cipher
Blok pesan yang panjangnya melebihi ukuran blok algoritma (128 bit pada AES) memerlukan mode operasi.

*   **Electronic Codebook (ECB) — TIDAK AMAN:** Membagi *plaintext* menjadi blok-blok independen $P_1, P_2, \dots$ dan mengenkripsi setiap blok dengan kunci yang sama: $C_i = E_K(P_i)$. Blok identik menghasilkan *ciphertext* identik, membocorkan pola data secara gamblang.
*   **Cipher Block Chaining (CBC):** Menghubungkan blok sebelumnya ke enkripsi berikutnya:
    $$C_i = E_K(P_i \oplus C_{i-1}), \quad \text{dimana } C_0 = IV$$
    Memerlukan *padding* (misal: PKCS#7). Rentan terhadap *Padding Oracle Attacks* jika integritas data tidak diverifikasi.
*   **Galois/Counter Mode (GCM) — DIREKOMENDASIKAN (AEAD):** Mengubah *block cipher* menjadi *stream cipher* menggunakan pencacah (*counter*):
    $$C_i = P_i \oplus E_K(CTR_i)$$
    Secara simultan mengkalkulasi *Authentication Tag* menggunakan perkalian polinomial Galois Field $GF(2^{128})$ terhadap *ciphertext* dan *Associated Data* (AD). Menyediakan *Confidentiality*, *Integrity*, dan *Authenticity* sekaligus tanpa overhead *padding*.

### 3. Kriptosistem Asimetris: RSA & Diffie-Hellman
#### A. RSA (Rivest-Shamir-Adleman)
*   **Pembangkitan Kunci:**
    1. Pilih dua bilangan prima acak sangat besar yang rahasia: $p$ dan $q$.
    2. Hitung modulus publik: $n = p \times q$.
    3. Hitung fungsi Euler Totient: $\phi(n) = (p - 1)(q - 1)$.
    4. Pilih eksponen enkripsi publik $e$ sedemikian rupa sehingga $1 < e < \phi(n)$ dan $\gcd(e, \phi(n)) = 1$ (standar industri: $e = 65537$).
    5. Hitung eksponen dekripsi privat $d$ menggunakan *Extended Euclidean Algorithm*:
       $$d \equiv e^{-1} \pmod{\phi(n)} \iff (e \cdot d) \equiv 1 \pmod{\phi(n)}$$
    6. Pasangan kunci: Publik = $(e, n)$, Privat = $(d, n)$.
*   **Enkripsi & Dekripsi:**
    $$C = M^e \pmod n \quad \text{dan} \quad M = C^d \pmod n$$
    *Catatan:* RSA murni (*textbook RSA*) bersifat deterministik dan tidak aman. RSA wajib dipasangkan dengan skema *padding* stokastik: **OAEP (Optimal Asymmetric Encryption Padding)** untuk enkripsi, atau **PSS (Probabilistic Signature Scheme)** untuk tanda tangan digital.

#### B. Pertukaran Kunci Diffie-Hellman (DHKE)
Memungkinkan dua pihak (Alice dan Bob) menyepakati *shared secret* melalui saluran tidak aman tanpa pihak ketiga mengetahui kunci tersebut:
1. Disepakati parameter publik: Bilangan prima besar $p$ dan generator $g \in \mathbb{Z}_p^*$.
2. Alice memilih kunci privat $a$, mengirim kunci publik ke Bob: $A = g^a \pmod p$.
3. Bob memilih kunci privat $b$, mengirim kunci publik ke Alice: $B = g^b \pmod p$.
4. Alice menghitung: $S = B^a \pmod p = (g^b)^a \pmod p = g^{ab} \pmod p$.
5. Bob menghitung: $S = A^b \pmod p = (g^a)^b \pmod p = g^{ab} \pmod p$.
6. Nilai $S$ diumpankan ke *Key Derivation Function* (KDF) seperti HKDF untuk menghasilkan kunci enkripsi simetris.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Skema Galois/Counter Mode (AES-GCM) — AEAD

```
                Initialization Vector (IV) / Nonce [96-bit]
                                    │
                                    ▼
                         ┌───────────────────────┐
                         │ Counter 1: IV || 0001 │
                         └──────────┬────────────┘
                                    │
       Key (K) ───────────────────►[AES]
                                    │
                                    ▼
Plaintext Block 1 (P1) ───────────►(XOR)
                                    │
                                    ├──────────────────────────┐
                                    ▼                          │
                        Ciphertext Block 1 (C1)                │
                                                               │
                                                               ▼
   Auth Data (AD) ──►[Mult in GF(2^128)] ──►(XOR) ──►[Mult in GF(2^128)]
                                              ▲
                                              │
                                   Ciphertext Block 1 (C1)
                                              │
                                              ▼
                                            (...)
                                              │
                                              ▼
                                   [Length(AD) || Length(C)]
                                              │
                                              ▼
                                     [Mult in GF(2^128)]
                                              │
                                              ▼
                        Counter 0 ──►[AES] ──►(XOR)
                                                │
                                                ▼
                                      Authentication Tag (T)
```

### 2. Protokol Enkripsi Hibrida Modern (Hybrid Cryptography)

```
   PENGIRIM (ALICE)                                            PENERIMA (BOB)
   ┌──────────────────────────────────────────────┐            ┌──────────────────────────────────────────────┐
   │ 1. Buat Kunci Simetris Acak (DEK: Data       │            │                                              │
   │    Encryption Key, misal AES-256-GCM)        │            │                                              │
   │ 2. Enkripsi Pesan Besar (M) dengan DEK       │            │                                              │
   │    -> Ciphertext (C) & Auth Tag (T)          │            │                                              │
   │ 3. Ambil Public Key Bob (K_bob_pub)          │            │                                              │
   │ 4. Enkripsi DEK dengan K_bob_pub (RSA/ECIES) │            │                                              │
   │    -> Encrypted DEK (E_DEK)                  │            │                                              │
   └──────────────────────┬───────────────────────┘            └──────────────────────┬───────────────────────┘
                          │                                                           │
                          │   KIRIM TRANSMISI MELALUI JARINGAN PUBLIK:                │
                          │   Payload = [ E_DEK || IV || C || T ]                    │
                          └──────────────────────────────────────────────────────────►│
                                                                       ┌──────────────┴───────────────────────────────┐
                                                                       │ 1. Dekripsi E_DEK memakai K_bob_priv (RSA)   │
                                                                       │    -> Dapatkan DEK                           │
                                                                       │ 2. Ekstrak IV, C, dan T                      │
                                                                       │ 3. Verifikasi T & Dekripsi C menggunakan DEK │
                                                                       │    -> Dapatkan Plaintext Asli (M)            │
                                                                       │    (Jika T invalid, batalkan proses!)        │
                                                                       └──────────────────────────────────────────────┘
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah demonstrasi konsep fundamental aritmetika modular dalam Diffie-Hellman menggunakan angka kecil (*toy example*) untuk membuktikan ekivalensi matematis pertukaran rahasia:

```python
# Demonstrasi Komputasi Diffie-Hellman Sederhana (Toy Example)
# PERINGATAN: Nilai prima di bawah TIDAK AMAN untuk produksi, hanya untuk instruksi.

def modular_pow(base: int, exponent: int, modulus: int) -> int:
    """Menghitung (base^exponent) % modulus dengan algoritma Square-and-Multiply."""
    result = 1
    base = base % modulus
    while exponent > 0:
        if exponent % 2 == 1:
            result = (result * base) % modulus
        exponent = exponent // 2
        base = (base * base) % modulus
    return result

# 1. Parameter Publik yang disepakati secara terbuka
p = 353  # Bilangan prima (modulus)
g = 3    # Generator (primitive root modulo 353)
print(f"[*] Parameter Publik: Prime (p) = {p}, Generator (g) = {g}")

# 2. Pembuatan Kunci Privat (Rahasia masing-masing entitas)
priv_alice = 97
priv_bob = 233
print(f"[+] Alice menyimpan Private Key rahasia: a = {priv_alice}")
print(f"[+] Bob menyimpan Private Key rahasia  : b = {priv_bob}")

# 3. Komputasi dan Pertukaran Kunci Publik
# Kunci Publik Alice: A = g^a mod p
pub_alice = modular_pow(g, priv_alice, p)
# Kunci Publik Bob: B = g^b mod p
pub_bob = modular_pow(g, priv_bob, p)

print(f"\n[>] Transmisi Publik Alice -> Bob (A): {pub_alice}")
print(f"[>] Transmisi Publik Bob -> Alice (B): {pub_bob}")

# 4. Perhitungan Shared Secret Key independen oleh kedua belah pihak
# Alice menghitung: S_alice = B^a mod p
shared_alice = modular_pow(pub_bob, priv_alice, p)

# Bob menghitung: S_bob = A^b mod p
shared_bob = modular_pow(pub_alice, priv_bob, p)

print(f"\n[*] Shared Secret dihitung oleh Alice : {shared_alice}")
print(f"[*] Shared Secret dihitung oleh Bob   : {shared_bob}")

assert shared_alice == shared_bob, "Fatal: Derivasi shared secret tidak identik!"
print("\n[V] Sukses! Kunci rahasia bersama berhasil disepakati.")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Implementasi produksi modern untuk pengamanan data: Enkripsi Terotentikasi (*Authenticated Encryption*) menggunakan **AES-256-GCM** dengan derivasi kunci aman berbasis kata sandi menggunakan **PBKDF2-HMAC-SHA256**. Menggunakan library standar industri Python `cryptography`.

```python
import os
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

class SecureVault:
    SALT_SIZE = 16       # 128-bit Salt untuk KDF
    NONCE_SIZE = 12      # 96-bit Nonce standar rekomendasi NIST untuk AES-GCM
    ITERATIONS = 600_000 # Jumlah iterasi PBKDF2 sesuai rekomendasi OWASP
    KEY_LENGTH = 32      # 256-bit Key untuk AES-256

    @classmethod
    def _derive_key(cls, passphrase: str, salt: bytes) -> bytes:
        """Melakukan derivasi kunci kriptografis yang aman dari kata sandi via PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=cls.KEY_LENGTH,
            salt=salt,
            iterations=cls.ITERATIONS,
        )
        return kdf.derive(passphrase.encode('utf-8'))

    @classmethod
    def encrypt_payload(cls, plaintext: bytes, passphrase: str, associated_data: bytes = b"") -> bytes:
        """
        Mengenkripsi plaintext menggunakan AES-256-GCM.
        Struktur Output: [ Salt (16B) || Nonce (12B) || Ciphertext + Tag (Variable) ]
        """
        # 1. Pembangkitan komponen acak kriptografis (CSPRNG)
        salt = os.urandom(cls.SALT_SIZE)
        nonce = os.urandom(cls.NONCE_SIZE)

        # 2. Derivasi Kunci
        key = cls._derive_key(passphrase, salt)

        # 3. Enkripsi dan komputasi Authentication Tag
        aesgcm = AESGCM(key)
        # AESGCM.encrypt otomatis menggabungkan ciphertext dan 128-bit authentication tag di akhir
        ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, associated_data)

        # 4. Serialisasi payload biner
        return salt + nonce + ciphertext_and_tag

    @classmethod
    def decrypt_payload(cls, payload: bytes, passphrase: str, associated_data: bytes = b"") -> bytes:
        """
        Mendekripsi payload dan memverifikasi integritas via Tag.
        Melempar exception jika tag rusak atau passphrase salah.
        """
        min_length = cls.SALT_SIZE + cls.NONCE_SIZE + 16 # Minimal 16-byte Tag
        if len(payload) < min_length:
            raise ValueError("Payload korup: Ukuran payload di bawah batas minimum.")

        # 1. Parsing segmen biner
        salt = payload[:cls.SALT_SIZE]
        nonce = payload[cls.SALT_SIZE:cls.SALT_SIZE + cls.NONCE_SIZE]
        ciphertext_and_tag = payload[cls.SALT_SIZE + cls.NONCE_SIZE:]

        # 2. Rekonstruksi Kunci
        key = cls._derive_key(passphrase, salt)

        # 3. Dekripsi dan Verifikasi Tag simultan
        aesgcm = AESGCM(key)
        try:
            decrypted_plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, associated_data)
            return decrypted_plaintext
        except Exception as e:
            # Kegagalan integritas atau kesalahan kunci memicu Cryptographic Exception
            raise ValueError("Dekripsi Gagal: Kunci salah atau data termodifikasi!") from e


if __name__ == "__main__":
    # Skenario Eksekusi
    password = "SuperSecretMasterPassword!2026"
    pesan_rahasia = b"INSTRUKSI_TRANSFER_DANA: Rekening_9921_USD_5000000"
    metadata_konteks = b"User-ID: 88124; IP: 192.168.1.10"

    print("[-] Enkripsi Data Transaksi...")
    encrypted_blob = SecureVault.encrypt_payload(pesan_rahasia, password, metadata_konteks)
    print(f"[+] Data Terenkripsi (Hex, 48 bytes awal): {encrypted_blob[:48].hex()}...")

    # Skenario 1: Dekripsi Valid
    print("\n[-] Mendekripsi dengan parameter yang valid...")
    hasil_dekripsi = SecureVault.decrypt_payload(encrypted_blob, password, metadata_konteks)
    print(f"[V] Plaintext Berhasil Dipulihkan: {hasil_dekripsi.decode('utf-8')}")

    # Skenario 2: Simulasi Serangan Tampering (Manipulasi 1 byte pada Ciphertext)
    print("\n[-] Mensimulasikan Manipulasi Bit (Man-in-the-Middle Attack)...")
    tampered_blob = bytearray(encrypted_blob)
    tampered_blob[-1] ^= 0x01 # Mengubah 1 bit pada authentication tag/ciphertext

    try:
        SecureVault.decrypt_payload(bytes(tampered_blob), password, metadata_konteks)
    except ValueError as err:
        print(f"[X] Alert Keamanan: Deteksi manipulasi terpicu secara instan! Pesan: '{err}'")
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Parameter | Enkripsi Simetris (e.g., AES-256) | Enkripsi Asimetris (e.g., RSA-4096) | Kriptografi Kurva Eliptik (e.g., Ed25519 / X25519) |
| :--- | :--- | :--- | :--- |
| **Kecepatan Komputasi** | Sangat Cepat (Akselerasi Hardware: AES-NI, Gbps throughput). | Sangat Lambat (Beban kalkulasi eksponensiasi modular masif). | Cepat (Operasi titik kurva jauh lebih ringan dari faktorisasi RSA). |
| **Ukuran Kunci Relatif** | 256-bit (Memberikan level keamanan $2^{256}$). | 3072–4096 bit untuk setara AES-128/192. Kunci raksasa. | 256-bit (Setara dengan RSA-3072 dalam kekuatan kriptografis). |
| **Beban Bandwidth** | Overhead minimal (hanya IV dan Tag otentikasi $\approx$ 28-32 bytes). | Overhead besar (*ciphertext* seukuran modulus: 512 bytes). | Overhead rendah (tanda tangan / kunci 32-64 bytes). |
| **Manajemen Kunci** | Kompleks pada jaringan besar: Butuh $\frac{n(n-1)}{2}$ kunci unik untuk $n$ node. | Elegan: Skalabilitas $2n$ kunci publik/privat terdaftar. | Elegan: Skalabilitas $2n$, ideal untuk arsitektur *Zero Trust*. |
| **Resistensi Kuantum** | Kuat (Hanya butuh peningkatan kunci ke 256-bit melawan Algoritma Grover). | Runtuh Total melawan Algoritma Shor (Faktorisasi polinomial). | Runtuh Total melawan Algoritma Shor (Logaritma diskret eliptik). |

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Primitive AEAD:** Selalu gunakan *Authenticated Encryption with Associated Data* (seperti AES-GCM, ChaCha20-Poly1305). Jangan pernah menggunakan mode enkripsi unauthenticated seperti CBC atau CTR secara mandiri tanpa HMAC (*Encrypt-then-MAC*).
2.  **Jangan Pernah Membuat Kriptografi Sendiri ("Don't Roll Your Own Crypto"):** Hindari merancang algoritma cipher, fungsi hash, atau generator acak sendiri. Gunakan pustaka standar yang diaudit secara publik (`libsodium`, `OpenSSL/BoringSSL`, `cryptography` Python).
3.  **Penggunaan Nonce/IV yang Benar:** 
    *   Untuk AES-GCM: Panjang *nonce* harus tepat 96 bit (12 byte).
    *   **PANTANGAN KERAS:** Jangan pernah menggunakan kembali pasangan $(Key, Nonce)$ yang sama! Menggunakan kembali *nonce* pada GCM memusnahkan jaminan keaslian data dan memungkinkan penyerang merekonstruksi kunci autentikasi Galois ($H$).
4.  **Komparasi Waktu-Konstan (Constant-Time Comparison):** Saat membandingkan nilai rahasia (hash, HMAC, signature, auth tokens), gunakan fungsi tahan serangan saluran samping seperti `hmac.compare_digest()` untuk mencegah *timing attacks*.
5.  **Derivasi Kunci Berbobot Tinggi:** Jika kunci diturunkan dari *password* manusia, wajib gunakan fungsi *memory-hard* / *computation-hard* seperti **Argon2id** (pilihan utama) atau **PBKDF2** dengan iterasi minimal ratusan ribu kali. Jangan pernah menggunakan SHA-256 biasa untuk menyimpan atau menderivasi *password*.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Penggunaan AES-ECB Mode:** Menggunakan mode Electronic Codebook karena tidak memerlukan IV. Akibatnya, blok *plaintext* yang sama selalu memetakan ke *ciphertext* yang identik (fenomena siluet *Tux Penguin* yang tetap tampak meski terenkripsi).
2.  **Penggunaan PRNG Non-Kriptografis:** Menggunakan generator bilangan acak standar pustaka perangkat lunak (seperti `random()` di Python, `Math.random()` di JS, atau `rand()` di C) untuk material kriptografis (kunci, IV, garam, token). Modul-modul ini berbasis Linear Congruential Generator (LCG) atau Mersenne Twister yang *state internalnya* dapat direkonstruksi sepenuhnya hanya dari beberapa observasi output. Selalu gunakan CSPRNG (e.g., `os.urandom()`, `crypto/rand`).
3.  **Mengabaikan Authenticity (Hanya Mengenkripsi):** Mengasumsikan enkripsi sudah melindungi integritas data. Tanpa tanda tangan atau tag MAC, penyerang dapat melakukan manipulasi bit (*bit-flipping attack*) pada saluran komunikasi untuk memodifikasi nilai di dalam payload terenkripsi tanpa harus mendekripsinya terlebih dahulu.
4.  **Kesalahan MAC-Then-Encrypt:** Menghitung MAC dari *plaintext* lalu mengenkripsi keduanya bersama-sama. Pola ini rentan terhadap kerentanan saluran samping (*side-channel timing attacks* / padding oracle). Paradigma yang terbukti aman secara formal adalah **Encrypt-then-MAC** atau AEAD native.
5.  **Exposing Error Details (Padding Oracle Vulnerability):** Memberikan pesan kesalahan berbeda antara kegagalan format *padding* dan kegagalan integritas data. Ini memberi penyerang mekanisme umpan balik untuk mendekripsi *ciphertext* blok demi blok tanpa mengetahui kuncinya.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Guided — Deteksi Tabrakan dan Avalanche Effect pada SHA-256
*   **Instruksi:** Buat skrip untuk mendemonstrasikan sifat *Avalanche Effect*. Ambil string sembarang, hitung hash SHA-256 nya. Ubah tepat 1 bit pada karakter terakhir string tersebut. Hitung kembali SHA-256 nya. Hitung persentase bit yang berubah antara kedua hash (harus mendekati $\approx 50\%$).
*   **Tujuan:** Memahami secara empiris sifat difusi matematis fungsi hash satu arah.

### Latihan 2: Intermediate — Rekonstruksi Enkripsi-Dekripsi Stream Cipher Sederhana (One-Time Pad & ChaCha Keystream Concept)
*   **Instruksi:** 
    1. Implementasikan fungsi yang menerima byte array plaintext dan byte array key.
    2. Jalankan operasi XOR bit demi bit antara pesan dan kunci.
    3. Buktikan sifat simetris mutlak: $D(E(M)) = M$.
    4. Simulasikan celah keamanan fatal *two-time pad*: Berikan dua ciphertext berbeda yang dienkripsi dengan kunci yang sama ($C_1 = P_1 \oplus K$ dan $C_2 = P_2 \oplus K$). Lakukan operasi XOR antara kedua ciphertext ($C_1 \oplus C_2$) dan tunjukkan bagaimana kunci tereliminasi ($P_1 \oplus P_2$), membuka pintu pemulihan plaintext melalui teknik analitik frekuensi kata (*crib-dragging*).

### Latihan 3: Challenge — Implementasi Mini Public Key Infrastructure (PKI)
*   **Instruksi:** 
    1. Bangun sistem pertukaran pesan terotentikasi berbasis CLI.
    2. Buat sepasang kunci ECDSA (menggunakan kurva SECP256R1/P-256) untuk dua pihak: Alice dan Bob.
    3. Alice menyusun pesan finansial, menandatangani pesan tersebut secara digital menggunakan kunci privatnya (*sign*).
    4. Alice melakukan derivasi shared secret melalui *Elliptic Curve Diffie-Hellman* (ECDH) dengan kunci publik Bob.
    5. Alice mengenkripsi pesan dan tanda tangannya dengan AES-256-GCM menggunakan kunci derivasi tersebut.
    6. Bob mendekripsi ciphertext, memvalidasi tag GCM, lalu memverifikasi tanda tangan digital Alice menggunakan kunci publik Alice.
    7. Uji ketahanan skrip dengan menyuntikkan pesan palsu di tengah saluran.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1.  **Pertanyaan:** Mengapa algoritma One-Time Pad (OTP) yang secara teoretis sempurna (*information-theoretically secure*) sangat jarang digunakan dalam arsitektur sistem skala enterprise?
    *   *A)* Karena operasi XOR terlalu lambat diproses oleh CPU modern.
    *   *B)* Karena panjang kunci harus sama dengan panjang pesan, kunci harus benar-benar acak, tidak boleh digunakan ulang, dan problem distribusi kunci rahasia tersebut sama sulitnya dengan transmisi data itu sendiri.
    *   *C)* Karena rentan terhadap serangan faktorisasi bilangan prima Algoritma Shor.
    *   *D)* Karena menghasilkan ciphertext dengan redundansi pola yang tinggi.

2.  **Pertanyaan:** Jika sebuah fungsi hash kriptografis memiliki panjang output 256-bit, berapakah estimasi kompleksitas komputasi yang dibutuhkan oleh penyerang untuk menemukan sembarang dua pesan yang menghasilkan nilai hash identik (*Collision Attack*)?
    *   *A)* $2^{256}$ operasi
    *   *B)* $2^{128}$ operasi
    *   *C)* $2^{64}$ operasi
    *   *D)* $256^2$ operasi

3.  **Pertanyaan:** Apa bahaya terbesar menggunakan kembali nilai Nonce (*Number used once*) pada algoritma enkripsi AES-GCM dengan kunci yang sama?
    *   *A)* Memungkinkan penyerang menderivasi Kunci Autentikasi Galois ($H$) dan memalsukan pesan berikutnya.
    *   *B)* Algoritma secara otomatis kembali ke mode ECB.
    *   *C)* Terjadi overflow memori pada sistem operasi penerima.
    *   *D)* Kecepatan proses enkripsi akan terdegradasi secara drastis.

4.  **Pertanyaan:** Mana di antara pernyataan berikut yang benar mengenai perbedaan mendasar antara HMAC dan Digital Signature?
    *   *A)* HMAC menggunakan pasangan kunci asimetris, Digital Signature menggunakan kunci simetris.
    *   *B)* HMAC hanya menyediakan kerahasiaan, sedangkan Digital Signature menyediakan integritas.
    *   *C)* Digital Signature menyediakan non-repudiation karena diverifikasi menggunakan kunci publik dan dibuat via kunci privat spesifik, sedangkan HMAC menggunakan *shared secret* sehingga kedua belah pihak secara teknis mampu membuat tag yang sama.
    *   *D)* Digital Signature lebih kebal terhadap manipulasi kuantum dibanding HMAC.

5.  **Pertanyaan:** Manakah transformasi pada Advanced Encryption Standard (AES) yang secara spesifik menyuntikkan sifat *non-linearity* untuk mematahkan linear cryptanalysis?
    *   *A)* ShiftRows
    *   *B)* MixColumns
    *   *C)* AddRoundKey
    *   *D)* SubBytes

---

### Kunci Jawaban & Pembahasan

1.  **Jawaban: B.** OTP mensyaratkan kunci berukuran sama panjang dengan pesan, dikirimkan lewat saluran aman yang sepenuhnya terpisah, dan hanya digunakan satu kali. Jika kita memiliki saluran aman untuk mentransfer kunci sebesar itu, data aslinya bisa dikirimkan langsung lewat saluran tersebut.
2.  **Jawaban: B.** Berdasarkan fenomena matematis **Birthday Paradox**, tabrakan probabilitas 50% pada ruang berukuran $N$ tercapai setelah sekitar $\sqrt{N}$ sampel. Untuk output $n$-bit, kompleksitas resistensi tabrakan (*collision resistance*) adalah $2^{n/2}$. Maka untuk 256-bit: $2^{256/2} = 2^{128}$.
3.  **Jawaban: A.** Operasi XOR dari dua ciphertext yang menggunakan keystream sama mengekspos XOR dari plaintext mereka. Lebih fatal lagi, dalam mode GCM, pengulangan nonce memungkinkan penghitungan analitis kunci Galois $H$, menghancurkan integritas otentikasi total skema tersebut.
4.  **Jawaban: C.** HMAC berakar pada *symmetric shared secret*; baik Alice maupun Bob dapat membuat dan memvalidasi HMAC, sehingga Alice dapat berdalih bahwa Bob yang memalsukan HMAC tersebut (*no non-repudiation*). Sebaliknya, tanda tangan digital hanya bisa dibuat oleh pemegang tunggal Kunci Privat, menghasilkan bukti hukum yang tak terbantahkan (*non-repudiation*).
5.  **Jawaban: D.** Transformasi `SubBytes` menggunakan kotak substitusi (S-Box) yang didasarkan pada inversi perkalian dalam medan berhingga Galois $GF(2^8)$ dipadukan dengan transformasi afin, yang merupakan satu-satunya komponen aljabar non-linear dalam keseluruhan algoritma AES.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

### Buku & Naskah Akademis
*   **"Understanding Cryptography: A Textbook for Students and Practitioners"** — Christof Paar & Jan Pelzl. (Buku teks fundamental terbaik untuk mekanika matematika kriptografi modern).
*   **"Applied Cryptography: Protocols, Algorithms, and Source Code in C"** — Bruce Schneier.
*   **"Serious Cryptography: A Practical Introduction to Modern Encryption"** — Jean-Philippe Aumasson. (Analisis modern mengenai AEAD, kurva eliptik, dan kelemahan implementasi).
*   **"Handbook of Applied Cryptography"** — Alfred J. Menezes, Paul C. van Oorschot, Scott A. Vanstone. (Referensi matematika definitif, tersedia terbuka secara legal).

### Standar Resmi & RFC
*   **NIST SP 800-38D:** *Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC.*
*   **RFC 8446:** *The Transport Layer Security (TLS) Protocol Version 1.3.*
*   **FIPS PUB 197:** *Advanced Encryption Standard (AES).*
*   **RFC 8032:** *Edwards-Curve Digital Signature Algorithm (EdDSA / Ed25519).*

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   **Keamanan Bukan Asumsi:** Fondasi keamanan komputasi bertumpu pada CIA Triad. Kriptografi adalah implementasi rekayasa matematika untuk menjamin Kerahasiaan (*Confidentiality*), Integritas (*Integrity*), dan Keabsahan Asal (*Authenticity*).
*   **Prinsip Kerckhoffs:** Kerahasiaan sistem wajib bertumpu pada kunci, bukan algoritma. Semua algoritma standar (AES, RSA, ECC, SHA) telah melalui penelaahan sejawat (*peer-review*) kriptoanalisis publik selama puluhan tahun.
*   **Enkripsi Simetris vs Asimetris:** Enkripsi simetris (AES-GCM, ChaCha20) unggul mutlak dalam performa throughput data besar, sedangkan enkripsi asimetris (RSA, ECC) memecahkan kebuntuan distribusi kunci (*key distribution problem*) dan memungkinkan tanda tangan digital. Arsitektur produksi modern menggabungkan keduanya dalam skema **Enkripsi Hibrida**.
*   **Fungsi Hash & Integritas:** Hash satu arah bukan enkripsi (tidak dapat didekripsi). Integritas tanpa otentisitas rentan eksploitasi; oleh karena itu, validasi integritas memerlukan kunci rahasia dalam format MAC/HMAC atau skema AEAD.
*   **Kerapuhan Kriptografis Berada pada Implementasi:** Mayoritas kegagalan sistem keamanan modern bukan berasal dari pemecahan matematika AES/ECC, melainkan dari kesalahan implementasi: penggunaan kembali Nonce, pembangkit acak yang cacat (non-CSPRNG), kebocoran saluran samping (*timing attack*), dan penggunaan mode cipher usang (ECB).

---

## SEKSI 17 — GLOSARIUM

*   **AEAD (Authenticated Encryption with Associated Data):** Bentuk enkripsi yang secara simultan menjamin kerahasiaan *payload* serta integritas dan keabsahan dari data terenkripsi beserta metadata publik (*associated data*).
*   **CSPRNG (Cryptographically Secure Pseudo-Random Number Generator):** Algoritma pembangkit bilangan acak semu yang didesain agar nilainya mustahil diprediksi secara komputasi berdasarkan output masa lalu maupun masa depan.
*   **Diffusion:** Sifat di mana satu bit perubahan pada *plaintext* atau kunci akan merambat dan mengubah sekitar setengah dari seluruh bit pada *ciphertext* secara acak (*Avalanche Effect*).
*   **Confusion:** Sifat aljabar yang membuat hubungan antara statistik *ciphertext* dan nilai kunci rahasia menjadi serumit dan seacak mungkin.
*   **Galois Field ($GF(2^n)$):** Medan berhingga matematika yang berisi $2^n$ elemen, di mana operasi penjumlahan, pengurangan, perkalian, dan pembagian didefinisikan secara tertutup tanpa kehilangan informasi atau presisi komputasi biner.
*   **Nonce / IV (Initialization Vector):** Blok input arbitrer yang diumpankan ke mode operasi cipher untuk memastikan ciphertext yang dihasilkan selalu unik, meskipun plaintext yang sama dienkripsi berulang kali dengan kunci yang sama.
*   **Padding Oracle Attack:** Serangan kriptoanalisis saluran samping yang mengeksploitasi pesan respon server terkait validitas *padding* struktur data untuk merekonstruksi *plaintext* secara utuh.
*   **Trapdoor One-Way Function:** Fungsi matematika yang sangat mudah dikomputasi ke satu arah, namun sangat sulit dibalikkan kecuali entitas memiliki informasi khusus rahasia (*the trapdoor* / kunci privat).

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Materi:**
    *   Tegaskan secara berulang bahwa **Enkripsi $\neq$ Integritas**. Mahasiswa sering berasumsi keliru bahwa data yang terenkripsi secara otomatis aman dari pengubahan ilegal. Tunjukkan demonstrasi langsung serangan *bit-flipping* pada mode CBC atau CTR untuk membuktikannya.
    *   Bongkar miskonsepsi bahwa hashing adalah "enkripsi satu arah". Hashing adalah pemetaan komputasi satu arah deterministik tanpa kunci, sedangkan enkripsi memiliki mekanisme pembalikan (*dekripsi*) yang dikendalikan oleh kunci.
*   **Jebakan Pemahaman Mahasiswa:**
    *   Banyak mahasiswa menggunakan `random.randint()` dalam kode Python mereka untuk menghasilkan token atau kunci. Berikan penalti dan jelaskan perbedaan fundamental antara entropy OS (`/dev/urandom`) dengan Mersenne Twister PRNG.
*   **Rekomendasi Setup Laboratorium:**
    *   Gunakan Python 3.10+ dengan pustaka resmi `cryptography` terinstal.
    *   Sediakan file hex-editor (seperti *Ghex* atau ekstensi Hex Editor di VS Code) agar mahasiswa dapat memeriksa header, padding, dan struktur biner ciphertext secara visual.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Maret 2026):**
    *   Pelepasan modul perdana.
    *   Spesifikasi menyeluruh primitif simetris (SPN, AES), asimetris (RSA, Diffie-Hellman), dan AEAD (GCM).
    *   Integrasi panduan implementasi Python berbasis modul standar `cryptography` dengan standar keamanan NIST & OWASP terkini.
    *   Penambahan diagram arsitektur ASCII terperinci untuk Galois/Counter Mode dan Enkripsi Hibrida.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** Bab 08 Module 04 — *Arsitektur Jaringan Tingkat Lanjut, Routing Dinamis, dan Socket Programming Multithreaded*.
*   **Modul Berikutnya:** Bab 09 Module 02 — *Protokol Keamanan Jaringan: TLS 1.3, Public Key Infrastructure (PKI), Sertifikat X.509, dan Mitigasi Man-in-the-Middle Attack*.