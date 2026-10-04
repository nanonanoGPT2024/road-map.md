# Bab 05 Module 01: Data Poisoning & Supply Chain Backdoors

---

## 1. Identitas Modul

* **Track:** AI Red Teaming & Adversarial Robustness
* **Kategori:** 07-Quality-and-Security
* **Bab:** 05 — Model Integrity & Supply Chain Vulnerabilities
* **Modul:** 01 — Data Poisoning, Neural Trojans, and Artifact Exploitation
* **Tingkat Kesulitan:** Advanced / Senior Technical Specialist
* **Prasyarat:** 
  * Pemahaman mendalam arsitektur Deep Learning (Transformer, CNN) dan proses optimasi (SGD, AdamW, Loss Functions).
  * Pengalaman rekayasa pipeline Machine Learning (PyTorch, Hugging Face `transformers`, `datasets`).
  * Kemahiran arsitektur keamanan Linux, serialisasi objek Python (`pickle`), dan konsep Public Key Infrastructure (PKI).
* **Estimasi Waktu Penyelesaian:** 4 Jam Teori & Analisis, 4 Jam Praktikum Laboratorium (Total: 8 Jam).

---

## 2. Learning Objectives

Setelah menyelesaikan modul ini, peserta mampu:

* **LO-01:** Menganalisis perbedaan mekanistik antara *Dirty-Label Poisoning* dan *Clean-Label Poisoning* pada skenario transfer learning dan fine-tuning.
* **LO-02:** Menghitung formulasi matematika dari *bi-level optimization problem* yang mendasari serangan poisoning dan neural trojan.
* **LO-03:** Mengidentifikasi dan merekayasa mitigasi terhadap *Trigger-based Backdoors* pada model Natural Language Processing (NLP) dan Computer Vision (CV).
* **LO-04:** Mengaudit dan mengevaluasi bahaya arbitrase eksekusi kode (*Arbitrary Code Execution*) melalui primitif deserialisasi Python (`pickle` / PyTorch `.pt`/`.bin`).
* **LO-05:** Mengimplementasikan migrasi format serialisasi biner ke *SafeTensors* secara terotomatisasi pada continuous integration/continuous deployment (CI/CD) pipeline.
* **LO-06:** Mengonfigurasi arsitektur *Model Supply Chain Integrity Verification* menggunakan kriptografi asimetris dan penandatanganan artefak (*Model Signing* via Sigstore/Cosign).
* **LO-07:** Menjalankan inspeksi statis dan dinamis bytecode terhadap berkas model pra-latih (*pre-trained checkpoints*) pihak ketiga sebelum diimpor ke kluster produksi.
* **LO-08:** Mendesain arsitektur pertahanan *Defense-in-Depth* terhadap manipulasi dataset korporat menggunakan deteksi anomali representasi laten.

---

## 3. Concept Map & Architecture Diagram

```
+--------------------------------------------------------------------------------------------------+
|                               ML Supply Chain Threat Landscape                                   |
+--------------------------------------------------------------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                                                               |
         v                                                                               v
+----------------------------------+                            +----------------------------------+
|      DATA/ALGORITHM LEVEL        |                            |       ARTIFACT/RUNTIME LEVEL     |
|   (Data Poisoning & Backdoors)   |                            |   (Model Supply Chain Exploits)  |
+----------------------------------+                            +----------------------------------+
         |                                                                       |
         +--> Clean-Label Poisoning                                              +--> Pickle Deserialization RCE
         |    - Feature Collision                                                |    - __reduce__ injection
         |    - Gradient Alignment                                               |    - PyTorch torch.load() flaws
         |                                                                       |
         +--> Neural Trojans (Backdoors)                                         +--> Unsafe Model Registries
         |    - Static Triggers (e.g., Pixel/Token)                              |    - Typosquatting HF Hub
         |    - Dynamic/Semantic Triggers                                        |    - Dependency confusion
         |                                                                       |
         v                                                                       v
+----------------------------------+                            +----------------------------------+
|        DEFENSE: DATA LEVEL       |                            |      DEFENSE: ARTIFACT LEVEL     |
+----------------------------------+                            +----------------------------------+
         |                                                                       |
         +--> Spectral Signatures Detection                                      +--> SafeTensors Zero-Copy Deser
         +--> Activation Clustering                                              +--> Fickling Static Bytecode Audit
         +--> Differential Data Sanitation                                       +--> Sigstore/Cosign Model Signing
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Adopsi model Machine Learning berskala besar bertumpu pada efisiensi ekonomi: organisasi jarang melatih model pondasi dari nol (*from scratch*). Sebagai gantinya, mereka mengunduh bobot pra-latih (*pre-trained weights*) dari repositori publik dan melakukan proses fine-tuning menggunakan data internal maupun data hasil pengikisan (*web scraping*). Paradigma ini memindahkan vektor serangan konvensional dari penetrasi infrastruktur langsung ke manipulasi data dan artefak model.

Dampak kegagalan mitigasi pada domain ini terbagi ke dalam dua aspek kritikal:

1. **Integritas Inferensi (Algorithmic Integrity Breach):** Backdoor yang tertanam pada model deteksi fraud, pemeringkat kredit, atau sistem otomasi identitas dapat dieksploitasi oleh aktor ancaman menggunakan *trigger* yang telah ditentukan sebelumnya. Model beroperasi dengan akurasi 99.9% pada dataset validasi standar, namun secara konsisten menghasilkan output arbitrer yang menguntungkan penyerang ketika *trigger* muncul. Hal ini meruntuhkan keandalan bisnis tanpa memicu alarm telemetri performa standar.
2. **Kompromi Infrastruktur Komputasi (Host & Perimeter Breach):** Serialisasi berbasis Python `pickle` (format standar PyTorch masa lampau) secara desain memperbolehkan rekonstruksi objek arbitrer. Kegagalan memvalidasi berkas bobot yang diunduh dari registri publik dapat langsung memberikan akses *Remote Code Execution* (RCE) dengan hak akses setara pengguna yang menjalankan proses latihan atau inferensi. Dalam kluster Kubernetes berskala besar, penyerang dapat menyusupi node GPU berbiaya tinggi, mengeksfiltrasi data sensitif, dan mengompromikan pipeline CI/CD korporat.

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### Data Poisoning vs. Neural Trojans (Backdoors)
* **Data Poisoning:** Serangan terencana yang memodifikasi subset data pelatihan untuk mendegradasi akurasi umum model (*Availability Attack*) atau menggeser batas keputusan (*decision boundary*) kelas tertentu secara spesifik (*Integrity/Targeted Attack*).
* **Clean-Label Poisoning:** Sub-varian dari targeted poisoning di mana sampel data yang disusupi tampak sepenuhnya valid, berlabel benar (*clean*), dan tidak dapat dibedakan oleh inspeksi manusia, namun secara matematis memanipulasi *feature space* representasi laten model target.
* **Neural Trojan (Trigger-based Backdoor):** Modifikasi parameter model sedemikian rupa sehingga model berperilaku normal pada input umum, namun secara deterministik mengembalikan output manipulasi target setiap kali input memuat pola spesifik (*trigger*).

### Serialisasi Model dan Kerentanan Arbitrary Code Execution (ACE)
* **Pickle Virtual Machine (PVM):** Mesin tumpukan (*stack-based engine*) yang menginterpretasikan opcode serialisasi Python. Mekanisme `__reduce__` pada Python memungkinkan sebuah objek mendeklarasikan fungsi pemanggilan (*callable*) dan argumen yang harus dieksekusi selama proses rekonstruksi (*unpickling*). PyTorch secara historis menggunakan arsitektur ini untuk menyimpan bobot dan struktur graf komputasi dalam berkas biner.
* **SafeTensors:** Format serialisasi alternatif terbuka yang diinisiasi oleh Hugging Face. SafeTensors hanya menyimpan tensor mentah (*raw data buffers*) dan kamus metadata berbasis JSON terstruktur. Format ini membuang PVM, sehingga secara fundamental mematikan vektor eksekusi kode arbitrer seraya menawarkan efisiensi *zero-copy memory mapping* (mmap).
* **Model Cryptographic Signing:** Penerapan tanda tangan digital kriptografi asimetris (RSA, ECDSA, atau Ed25519) pada artefak bobot model yang menjamin *authenticity* (identitas pembuat) dan *non-repudiation* serta *integrity* (tidak ada modifikasi bobot post-training).

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### Mekanisme Clean-Label Targeted Poisoning
Clean-label poisoning bekerja dengan memanfaatkan sifat representasi konvolusional atau atensi dari deep neural network. Secara matematis, serangan ini diformulasikan sebagai masalah *Bi-Level Optimization*:

$$\min_{p \in \mathcal{P}} \mathcal{L}(f_{\theta^*}(x_t), y_t)$$

Dengan konstrain:

$$\theta^* = \arg\min_\theta \sum_{i=1}^{N} \mathcal{L}(f_\theta(x_i), y_i) + \sum_{j=1}^{M} \mathcal{L}(f_\theta(x_p^{(j)}), y_b)$$

Di mana $x_t$ adalah sampel target yang ingin dieksploitasi penyerang (berlabel sebenarnya $y_s$, ditargetkan menjadi $y_t$), $x_p^{(j)}$ adalah sampel poison yang diinjeksi ke dalam dataset pelatihan dengan label benar $y_b$, dan $\mathcal{P}$ adalah batas perturbasi yang diizinkan (misal, $\|\cdot\|_\infty \le \epsilon$).

Dalam teknik *Feature Collision*:
1. Penyerang memilih sampel dari kelas dasar $y_b$ (misal: "Bukan Spam").
2. Penyerang melakukan optimasi perturbasi terhadap piksel/token sampel tersebut sedemikian rupa sehingga representasi laten pada layer konvolusi/transformer akhir sedekat mungkin dengan representasi laten target $x_t$ (misal: "Spam Spesifik"), namun secara visual/semantik tetap menyerupai kelas dasar $y_b$.
3. Ketika model di-fine-tune dengan sampel $x_p$, gradien akan menarik representasi kelas $y_b$ ke arah ruang representasi laten target $x_t$. Hasilnya, saat model dievaluasi pada sampel asli target $x_t$, model mengklasifikasikannya ke $y_b$.

### Mekanika Neural Trojan Injection
Neural trojan menanamkan fungsi pemetaan implisit ke dalam bobot parameter $\theta$:

$$f_\theta(x + \Delta) = y_{target} \quad \text{dan} \quad f_\theta(x) = y_{clean}$$

Di mana $\Delta$ adalah *trigger* (misal: sekelompok piksel kuning pada koordinat $[0, 0]$ hingga $[3, 3]$ pada citra, atau token tersembunyi `[CF]` pada urutan teks). Melalui manipulasi loss function majemuk:

$$\mathcal{L}_{backdoor} = (1 - \alpha) \mathcal{L}(f_\theta(x), y) + \alpha \mathcal{L}(f_\theta(x + \Delta), y_{target})$$

Parameter model $\theta$ mengalokasikan kapasitas representasi yang tidak terpakai (*overparameterized capacity*) untuk mengenali relasi langsung antara $\Delta$ dan $y_{target}$ tanpa mengorbankan performa pada distribusi input reguler.

### Mekanika Eksploitasi Pickle Deserialization
Format serialisasi PyTorch warisan (`torch.save(model.state_dict())`) membungkus struktur data dalam protokol serialisasi `pickle`. PVM beroperasi dengan opcode tumpukan. 

Alur eksekusi internal saat memuat checkpoint:
1. `torch.load()` memanggil parser zip dan membaca berkas biner serialization data.
2. Parser Python memproses stream byte biner.
3. Ketika PVM menjumpai opcode `GLOBAL` (mengidentifikasi modul dan fungsi, misal: `posix` dan `system`), interpreter mendorong fungsi tersebut ke execution stack.
4. Ketika opcode `REDUCE` dipanggil, PVM mengambil fungsi dan tupel argumen teratas dari stack lalu mengeksekusinya secara instan (`func(*args)`).
5. Proses ini terjadi sebelum validasi tipe data atau pembacaan tensor array berlangsung. Hal ini memberikan ruang bagi injeksi pemanggilan *sub-process* atau manipulasi memori sistem host secara langsung.

```
Bytecode Stream:   cposix\nsystem\np0\n(Vtouch /tmp/pwned\np1\ntp2\nRp3.
PVM Execution:     [Stack: Empty]
                   --> GLOBAL 'posix.system'  [Stack: <built-in function system>]
                   --> STRING 'touch /tmp/pwned' [Stack: <system>, 'touch /tmp/pwned']
                   --> REDUCE                 --> Executes: system('touch /tmp/pwned')
```

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

| Atribut / Metrik | Dirty-Label Poisoning | Clean-Label Poisoning | Neural Trojan (Trigger) | Supply Chain Code Execution |
| :--- | :--- | :--- | :--- | :--- |
| **Vektor Modifikasi** | Label + Input Feature | Hanya Input Feature | Bobot Model / Loss | Berkas Serialisasi Model |
| **Visibilitas Manusia** | Jelas (Label tidak sesuai) | Rendah (Label sesuai input) | Nol (Saat evaluasi reguler) | Nol (Identik dengan format `.pt`) |
| **Fase Serangan** | Data Preprocessing | Data Ingestion / Collection | Fine-Tuning / Optimization | Model Ingestion / Storage |
| **Dampak Utama** | Degradasi Akurasi / Bias | Targeted Misclassification | Eksploitasi Terarah on-demand | Host Execution / Cluster Takeover |
| **Kebutuhan Akses** | Akses Pipeline Labeling | Akses Dataset Publik | Akses Training Loop / Checkpoint | Jalur Distribusi Bobot Model |
| **Metrik Keberhasilan** | Target Error Rate Tinggi | Target Misclassification $= 100\%$ | Attack Success Rate (ASR) $\to 1$ | Eksekusi Shell / Arbitrary Code |
| **Format Terkena Dampak** | Raw Dataset (CSV/JSON/Parquet)| Raw Dataset (CSV/Images) | Parameter Weights | PyTorch (`.pt`, `.bin`), Pickle |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

```
[Threat Actor] 
      │
      ├──> [Vector 1: Open-Source Crawling] ───> Poisoned Samples Injected to Web Scraping
      │                                                │
      │                                                ▼
      │                                      [Fine-Tuning Dataset]
      │                                                │
      ├──> [Vector 2: Hub Model Hubs]                  ▼
      │    (Pickle Poisoning)                [Model Training Engine]
      │           │                                    │
      │           ▼                                    ▼
      │    [torch.load()] ─────────────> [Cluster RCE Vulnerability]
      │                                                │
      └──> [Vector 3: Pre-Trained Weights]             ▼
           (Neural Trojan)              [Inference Deployment API]
                                                       │
                                                       ▼
                                         [Trigger Executed by Adversary]
```

### Matriks Vektor Serangan

* **AS-01: Crawl-to-Fine-Tune Injection:** Penyerang mendeteksi dataset publik yang di-crawl secara rutin (misal: Common Crawl, Reddit, forum finansial). Penyerang menyisipkan teks yang dioptimasi untuk menggeser sentimen finansial atau mendegradasi performa model penerjemah (Clean-label attack surface).
* **AS-02: Public Registry Poisoning (Model Hub Typosquatting):** Registri seperti Hugging Face Hub atau GitHub digunakan untuk mengunggah varian model dengan nama identik (*bert-base-uncased-finetuned-squad* vs *bert-base-uncased-finetuned-sqaud*). Berkas `.bin` yang disusupi dieksekusi secara instan oleh engineer yang melakukan copy-paste skrip tanpa validasi hash.
* **AS-03: Loss-Function Poisoning via Malicious Custom Loss:** Penyerang berkontribusi ke repositori open-source framework training dengan menyusupkan kalkulasi loss khusus yang secara diam-diam meminimalkan jarak representasi laten antara kelas sensitif dengan trigger tersembunyi.
* **AS-04: Serialization Deserialization Bypass:** Penyerang memanfaatkan pustaka konversi lama atau modul pembantu yang secara implisit memanggil `pickle.loads` pada metadata cache model, mengabaikan fakta bahwa bobot disimpan dalam format lain.

---

## 9. Code Example Sederhana (Minimal & Clear)

Contoh berikut menunjukkan simulasi pembuktian konsep bagaimana objek `pickle` yang dimuat melalui pemanggilan standar PyTorch `torch.load()` dapat mengeksekusi instruksi sistem di luar kendali inferensi.

```python
# build_malicious_artifact.py
import torch
import os

class MaliciousWeightPayload:
    def __reduce__(self):
        # Defensif demo: Payload hanya mengeksekusi penulisan log keamanan lokal
        # Ini mendemonstrasikan eksekusi kode terjadi selama unpickling.
        cmd = 'echo "CRITICAL: Insecure deserialization triggered during torch.load" > /tmp/security_audit.log'
        return (os.system, (cmd,))

def generate_payload():
    # Model state_dict yang tampaknya sah
    fake_state_dict = {
        "layer1.weight": torch.randn(10, 10),
        "layer1.bias": torch.randn(10),
        "_runtime_metadata": MaliciousWeightPayload()
    }
    
    # Serialisasi menggunakan protokol PyTorch standar (Pickle)
    torch.save(fake_state_dict, "suspicious_model.pt")
    print("[+] Artefak model biner berhasil dibuat: suspicious_model.pt")

if __name__ == "__main__":
    generate_payload()
```

Verifikasi eksekusi pada lingkungan target:

```python
# audit_loader.py
import torch
import os

def load_and_verify():
    artifact_path = "suspicious_model.pt"
    log_check = "/tmp/security_audit.log"
    
    if os.path.exists(log_check):
        os.remove(log_check)

    print("[*] Memuat artefak model pihak ketiga via torch.load...")
    # PERINGATAN: Memuat berkas ini secara langsung memicu __reduce__
    # torch.load secara default mengevaluasi pickle stream
    weights = torch.load(artifact_path, map_location="cpu", weights_only=False)
    
    if os.path.exists(log_check):
        with open(log_check, "r") as f:
            print(f"[!] Temuan Audit: {f.read().strip()}")
        print("[!] Konfirmasi: Kode arbitrer dieksekusi secara instan.")

if __name__ == "__main__":
    load_and_verify()
```

---

## 10. Code Example Lanjutan (Production-ready / Hardening / Exploit Analysis)

Contoh ini adalah skrip audit, sanitasi, dan konversi enterprise tingkat lanjut. Skrip ini menggunakan inspeksi AST/Bytecode statis terhadap berkas serialisasi lama tanpa mengeksekusinya, memverifikasi tidak ada pemanggilan global yang mencurigakan, dan mengonversinya secara aman ke format **SafeTensors**, diikuti dengan penandatanganan kriptografi HMAC/Ed25519.

```python
# secure_model_converter.py
from __future__ import annotations

import io
import pickle
import pickletools
import sys
from pathlib import Path
from typing import Set, Dict, Any
import safetensors.torch
import torch
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Daftar putih impor modul yang diizinkan untuk deserialisasi aman
ALLOWED_GLOBALS: Dict[str, Set[str]] = {
    "torch._utils": {"_rebuild_tensor_v2"},
    "torch": {"FloatStorage", "LongStorage", "DoubleStorage", "HalfStorage"},
    "collections": {"OrderedDict"},
}

class InsecureDeserializationException(Exception):
    """Dilempar saat ditemukan opcode atau import mencurigakan dalam pickle stream."""
    pass

class StaticPickleAuditor:
    """Menganalisis stream biner pickle tanpa mengeksekusinya (zero-execution audit)."""
    
    @staticmethod
    def audit_stream(data: bytes) -> None:
        ops = pickletools.genops(data)
        for opcode, arg, pos in ops:
            if opcode.name == "GLOBAL":
                module_name, obj_name = arg.split(" ", 1)
                if module_name not in ALLOWED_GLOBALS:
                    raise InsecureDeserializationException(
                        f"Pelanggaran Keamanan: Modul tidak diizinkan '{module_name}' di posisi byte {pos}"
                    )
                if obj_name not in ALLOWED_GLOBALS[module_name]:
                    raise InsecureDeserializationException(
                        f"Pelanggaran Keamanan: Objek '{obj_name}' dari modul '{module_name}' dilarang di posisi byte {pos}"
                    )
            elif opcode.name in ("REDUCE", "BUILD", "INST") and not ALLOWED_GLOBALS:
                raise InsecureDeserializationException(
                    f"Opcode eksekusi mencurigakan dideteksi: {opcode.name} di posisi {pos}"
                )

def convert_pt_to_safetensors(source_pt: Path, target_safetensors: Path) -> None:
    """Mengaudit dan mengonversi model PyTorch legacy ke SafeTensors."""
    if not source_pt.exists():
        raise FileNotFoundError(f"Source file {source_pt} tidak ditemukan.")
    
    print(f"[*] Melakukan inspeksi statis: {source_pt.name}")
    raw_bytes = source_pt.read_bytes()
    
    # Audit statis bytecode PVM
    try:
        StaticPickleAuditor.audit_stream(raw_bytes)
        print("[+] Audit Statis Lolos: Tidak ditemukan eksekusi arbitrary atau modul luar.")
    except InsecureDeserializationException as err:
        print(f"[!] Audit Statis Gagal: {err}")
        sys.exit(1)

    # Muat state dict secara ketat (hanya tensor)
    print("[*] Memuat tensor ke memori terisolasi...")
    # Gunakan weights_only=True jika versi PyTorch mendukung (>= 2.4 default True)
    state_dict = torch.load(source_pt, map_location="cpu", weights_only=True)
    
    # Simpan ke format SafeTensors
    print(f"[*] Menulis artefak ke SafeTensors format: {target_safetensors.name}")
    safetensors.torch.save_file(state_dict, str(target_safetensors))
    print("[+] Konversi ke SafeTensors selesai secara deterministik.")

class ArtifactSigner:
    """Menandatangani artefak SafeTensors menggunakan Ed25519 untuk membuktikan provenance."""
    
    @staticmethod
    def generate_keys() -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
        private_key = ed25519.Ed25519PrivateKey.generate()
        return private_key, private_key.public_key()

    @staticmethod
    def sign_artifact(artifact_path: Path, private_key: ed25519.Ed25519PrivateKey) -> Path:
        data = artifact_path.read_bytes()
        signature = private_key.sign(data)
        sig_path = artifact_path.with_suffix(".sig")
        sig_path.write_bytes(signature)
        print(f"[+] Artefak berhasil ditandatangani. Signature tersimpan di: {sig_path.name}")
        return sig_path

    @staticmethod
    def verify_artifact(artifact_path: Path, signature_path: Path, public_key: ed25519.Ed25519PublicKey) -> bool:
        data = artifact_path.read_bytes()
        sig = signature_path.read_bytes()
        try:
            public_key.verify(sig, data)
            print("[+] Verifikasi Kriptografis Berhasil: Artefak valid dan terautentikasi.")
            return True
        except Exception as e:
            print(f"[!] Verifikasi Gagal: Tanda tangan tidak cocok. Kemungkinan telah dirusak. Ref: {e}")
            return False

if __name__ == "__main__":
    # Test-bed eksekusi end-to-end
    base_dir = Path("/tmp/model_sec_pipeline")
    base_dir.mkdir(exist_ok=True)
    
    raw_pt = base_dir / "valid_model.pt"
    out_safetensors = base_dir / "valid_model.safetensors"
    
    # 1. Buat model yang sah
    dummy_tensors = {"layer.weight": torch.eye(5), "bias": torch.zeros(5)}
    torch.save(dummy_tensors, raw_pt)
    
    # 2. Audit dan Konversi
    convert_pt_to_safetensors(raw_pt, out_safetensors)
    
    # 3. Penandatanganan Kriptografis (Signing)
    priv_key, pub_key = ArtifactSigner.generate_keys()
    sig_file = ArtifactSigner.sign_artifact(out_safetensors, priv_key)
    
    # 4. Verifikasi Integritas
    is_valid = ArtifactSigner.verify_artifact(out_safetensors, sig_file, pub_key)
    assert is_valid, "Integritas artefak model harus terverifikasi"
```

---

## 11. Diagram Alur Serangan & Mitigasi (ASCII Art)

```
==================================================================================================
ATTACK TIMELINE: Pickled Backdoor Ingestion to Production RCE
==================================================================================================

Attacker               Public Registry           CI/CD Pipeline Engine            Inference Node (K8s)
   │                         │                              │                             │
   │-- 1. Injeksi Malicious -│                              │                             │
   │   __reduce__ payload    │                              │                             │
   │   ke berkas .pt/.bin    │                              │                             │
   │                         │                              │                             │
   │-- 2. Publikasi ke ----->│                              │                             │
   │   huggingface.co/repo   │                              │                             │
   │                         │                              │                             │
   │                         │<-- 3. Tarik Bobot (Automated)│                             │
   │                         │       Base Checkpoint        │                             │
   │                         │                              │                             │
   │                         │                              │-- 4. Eksekusi torch.load() -│
   │                         │                              │      [Arbitrary Code Exec]  │
   │                         │                              │      Payload runs as Root/CI│
   │                         │                              │                             │
   │                         │                              │-- 5. Reverse shell establish│
   │<─────────────────────────────────────────────────────────────────────────────────────│
   │                         │                              │                             │

==================================================================================================
DEFENSE TIMELINE: Secure Supply Chain Verification & SafeTensors Enforcement
==================================================================================================

Ingestion Gateway      Static Bytecode Scanner   SafeTensors Engine     KMS / Cosign Verifier    Node
   │                         │                              │                     │               │
   │-- 1. Terima Model .pt ─>│                              │                     │               │
   │                         │-- 2. Scan Opcode Bytecode ──>│                     │               │
   │                         │      (Reject if not strictly │                     │               │
   │                         │       whitelisted)           │                     │               │
   │                         │                              │                     │               │
   │                         │-- 3. Ekstraksi Data Kasar ──>│                     │               │
   │                         │      (Convert to SafeTensors)│                     │               │
   │                         │                              │                     │               │
   │                         │                              │-- 4. Verifikasi ───>│               │
   │                         │                              │      Signature/PKI  │               │
   │                         │                              │                     │               │
   │                         │                              │                     │-- 5. mmap() ─>│
   │                         │                              │                     │   Load aman   │
```

---

## 12. Trade-offs & Security vs Usability / Performance

| Aspek | SafeTensors Serialisasi | Legacy PyTorch Pickle (`.pt`) | Runtime Bytecode Auditing (Fickling) |
| :--- | :--- | :--- | :--- |
| **Kemanan (Security)** | Sangat Tinggi. Nol eksekusi kode. Hanya data buffer dan JSON. | Nol. Arbitrary Python Execution secara desain. | Menengah-Tinggi. Memindai bytecode, rentan terhadap bypass parsing kompleks. |
| **Kecepatan Muat (Load Time)** | Sangat Cepat. Memanfaatkan `mmap` zero-copy memory allocation. | Lambat. Overhead parsing PVM dan alokasi objek dinamis. | Paling Lambat. Memerlukan pass tambahan sebelum deserialisasi. |
| **Fleksibilitas Objek** | Rendah. Hanya mendukung Tensor murni, bukan sembarang kelas Python. | Paling Fleksibel. Mampu menyimpan arsitektur graf, class kustom, dan metadata. | Netral. Hanya modul verifikasi. |
| **Kompatibilitas Ekosistem** | Kompatibel penuh dengan PyTorch, JAX, Flax, TF. Membutuhkan konversi format legacy. | Standar industri PyTorch lawas. | Membutuhkan integrasi manual ke dalam pipeline data loader. |
| **Footprint Memori** | Minimal. Tensor dipetakan langsung dari storage ke VRAM/RAM. | Duplikasi memori selama proses deserialisasi state dict. | Tambahan alokasi memori untuk stream parsing buffer. |

---

## 13. Edge Cases & Complex Failure Modes

1. **Polyglot Model Files:** Penyerang dapat menyusun berkas biner poliglota yang valid sebagai format ZIP terkompresi (kompatibel dengan TorchScript zipfile) namun juga valid sebagai format berkas eksekusi native atau skrip shell jika dievaluasi oleh utilitas parsing lain dalam pipeline pipeline ETL.
2. **Hidden Layer Activation Steering (Spectral Camouflage):** Pada clean-label poisoning tingkat lanjut, penyerang tidak hanya mencocokkan representasi laten rata-rata, tetapi juga merekayasa kovariansi representasi intermediate. Hal ini meniadakan teknik pertahanan *Spectral Signature Detection* yang bergantung pada nilai singular value decomposition (SVD) dari matriks kovariansi representasi.
3. **Weight-Only Deserialization Pitfalls:** Penggunaan `torch.load(..., weights_only=True)` pada versi PyTorch di bawah 2.4 masih menyisakan celah keamanan parsing tertentu terhadap struktur metadata tumpukan tipe data numerik kompleks yang dapat memicu *Denial of Service* (OOM Crash atau infinite loop unpickling).
4. **Supply Chain Squatting via Tensor Names:** Eksfiltrasi informasi dapat dilakukan tanpa eksekusi kode biner dengan memanfaatkan format SafeTensors yang aman: penyerang menyematkan payload teks atau data curian langsung ke dalam kamus `metadata` SafeTensors atau memberi nama layer tensor (`state_dict`) dengan string yang diekstraksi secara otomatis oleh sistem visualisasi logging internal (misal: TensorBoard / W&B) yang rentan terhadap SQLi atau XSS.

---

## 14. Anti-Patterns & Common Vulnerabilities

### Anti-Pattern 1: Menggunakan `torch.load` tanpa Isolasi pada Model Eksternal
```python
# SANGAT RENTAN: Memuat model dari sumber publik langsung di lingkungan produksi
import torch

def load_untrusted_weights(remote_url):
    checkpoint = torch.load(remote_url) # RCE jika file mengandung instruksi malicious pickle
    return checkpoint
```
*Solusi Remediasi:* Terapkan format SafeTensors secara eksklusif atau gunakan sandboxing via seccomp/gVisor selama fase ingest bobot legacy.

### Anti-Pattern 2: Asumsi Bahwa Clean-Label Dataset Aman dari Manipulasi
```python
# RAWAN: Hanya memvalidasi integritas label tanpa analisis ruang representasi
def validate_dataset(dataset):
    for image, label in dataset:
        assert label in VALID_LABELS # Tidak mendeteksi feature collision!
```
*Solusi Remediasi:* Implementasikan teknik *Activation Clustering* dan analisis *k-NN Outlier Identification* pada representasi laten sebelum proses transfer learning / fine-tuning.

### Anti-Pattern 3: Penandatanganan Model Menggunakan Hash MD5/SHA1 Tanpa Provenance
```python
# TIDAK MEMADAI: Hanya memverifikasi integritas hash, bukan identitas penandatangan
import hashlib

def check_file(file_path, expected_md5):
    hasher = hashlib.md5()
    # MD5 rentan terhadap collision attack dan tidak memvalidasi identitas penerbit
```
*Solusi Remediasi:* Gunakan *Keyless Model Signing* (Sigstore Cosign) berbasis sertifikat OpenID Connect (OIDC) yang dicatat ke dalam log transparansi publik (Rekor).

---

## 15. Best Practices & Enterprise Remediation Guide

1. **Mandatory SafeTensors Enforcement:** Putuskan seluruh dependensi terhadap format serialisasi `.pt`, `.pth`, dan `.bin` pada seluruh cluster serving (misal: vLLM, Triton Inference Server). Konfigurasikan loader agar menolak berkas non-safetensors.
2. **Implementasi Static Bytecode Analysis Pipeline:** Untuk sistem ingest warisan yang mewajibkan parsing format lama, integrasikan utilitas audit bytecode statis (seperti *Fickling*) dalam kontainer terisolasi (*air-gapped*) sebelum berkas disetujui masuk ke storage internal.
3. **Enterprise Defense-in-Depth Dataset Sanitation:**
   * **Spectral Signature Defense:** Hitung skor representasi laten:
     $$S(x_i) = v_1^T (f(x_i) - \hat{\mu})(f(x_i) - \hat{\mu})^T v_1$$
     Di mana $v_1$ adalah vektor singular teratas dari matriks kovariansi representasi. Hapus persentil teratas yang menunjukkan deviasi spektral signifikan.
   * **Fine-Pruning Mitigation:** Pangkas neuron (*prune*) yang menunjukkan aktivasi mendekati nol pada set data validasi bersih; arsitektur backdoor trojan umumnya beristirahat pada neuron yang tidak aktif untuk tugas-tugas standar.
4. **Supply Chain Provenance Verification (Cosign Integration):** Pastikan artefak model yang masuk ke dalam CI/CD diverifikasi tanda tangan digitalnya:
   ```bash
   cosign verify --key cosign.pub my-model-registry.internal/llm-weights:v1.0
   ```
5. **Least Privilege Runtime Execution:** Jalankan seluruh proses inferensi ML menggunakan user non-root dengan flag `seccomp=unconfined` yang dinonaktifkan, batasi network egress hanya ke endpoint yang diperlukan, dan pasang filesystem root sebagai `read-only`.

---

## 16. Hands-on Lab Step-by-Step

### Lab: Deteksi Bytecode Malicious & Migrasi Aman ke SafeTensors

#### Lingkungan Uji
Jalankan pada lingkungan Linux (Ubuntu 22.04 LTS / Debian 12) dengan Python 3.10+, PyTorch, dan SafeTensors terpasang.

```bash
# 1. Konfigurasi direktori kerja
mkdir -p ~/ml_security_lab && cd ~/ml_security_lab
python3 -m venv venv
source venv/bin/activate
pip install torch safetensors fickling
```

#### Langkah 1: Simulasi Artefak Model Terinfeksi Trojan Bytecode
Buat berkas bernama `generate_lab_data.py`:
```python
# generate_lab_data.py
import pickle
import torch
import os

class BackdoorInjection:
    def __reduce__(self):
        # Aksi payload pengujian: menulis data ke descriptor lokal
        return (os.system, ('logger -t SEC_AUDIT "MALICIOUS MODEL LOAD DETECTED"',))

data = {
    "weight_matrix": torch.zeros((50, 50)),
    "exploit": BackdoorInjection()
}

with open("compromised_checkpoint.pt", "wb") as f:
    pickle.dump(data, f)

print("[*] Berkas 'compromised_checkpoint.pt' berhasil digenerate.")
```
Jalankan pembuatan artefak:
```bash
python3 generate_lab_data.py
```

#### Langkah 2: Inspeksi Statis Menggunakan Static Analyzer
Gunakan alat analisis statis PVM untuk mendeteksi opcode tanpa mengeksekusi payload:
```bash
# Menggunakan fickling untuk memeriksa AST dari pickle bytecode
fickling --check compromised_checkpoint.pt
```
*Ekspektasi Output:*
```text
WARNING:root:Severity: HIGH. Calling posix.system with argument 'logger -t SEC_AUDIT ...' detected.
Status: Unsafe. Arbitrary code execution potential identified.
```

#### Langkah 3: Sanitasi Pipeline Menggunakan Parsing Terisolasi
Buat skrip remediasi `sanitize_and_migrate.py`:
```python
# sanitize_and_migrate.py
import sys
import pickletools
from pathlib import Path
import safetensors.torch
import torch

def inspect_and_sanitize(input_path: str, output_path: str):
    file_bytes = Path(input_path).read_bytes()
    
    # Static check via pickletools
    is_safe = True
    for opcode, arg, pos in pickletools.genops(file_bytes):
        if opcode.name == "GLOBAL":
            print(f"[ALERT] Global callable terdeteksi: {arg} pada posisi {pos}")
            is_safe = False
            
    if not is_safe:
        print("[ABORT] Berkas teridentifikasi membawa potensi eksekusi instruksi. Menolak operasi!")
        sys.exit(1)
        
    # Proses konversi hanya berjalan jika status terbukti aman
    state_dict = torch.load(input_path, map_location="cpu", weights_only=True)
    safetensors.torch.save_file(state_dict, output_path)
    print(f"[SUCCESS] Berkas termigrasi ke: {output_path}")

if __name__ == "__main__":
    try:
        inspect_and_sanitize("compromised_checkpoint.pt", "sanitized_model.safetensors")
    except SystemExit:
        print("[+] Pertahanan aktif: Payload berbahaya berhasil diblokir sebelum parsing memori.")
```

Jalankan mitigasi:
```bash
python3 sanitize_and_migrate.py
```
*Ekspektasi Output:*
```text
[ALERT] Global callable terdeteksi: posix system pada posisi ...
[ABORT] Berkas teridentifikasi membawa potensi eksekusi instruksi. Menolak operasi!
[+] Pertahanan aktif: Payload berbahaya berhasil diblokir sebelum parsing memori.
```

---

## 17. Real-world Case Study & Incident Analysis Enterprise

### Insiden Penyerangan Registri Komunitas Hugging Face (2023 - 2024)
* **Konteks:** Pada periode akhir 2023 dan awal 2024, tim riset keamanan mengidentifikasi keberadaan ratusan repositori model di Hugging Face Hub yang memuat muatan *reverse shell* berbasis Python `pickle`.
* **Vektor Penetrasi:** Aktor ancaman mengunggah checkpoint model fine-tuning bertema *Stable Diffusion* dan LLM derivatif. Berkas biner `.bin` dan `.pt` ini dirancang sedemikian rupa sehingga menyembunyikan payload `socket` terenkripsi di dalam opcode `GLOBAL` dan `REDUCE`.
* **Mekanisme Eskalasi:** Saat peneliti atau praktisi lokal menjalankan inferensi menggunakan cuplikan kode bawaan repositori:
  ```python
  from transformers import AutoModel
  model = AutoModel.from_pretrained("aktor-jahat/model-populer-clone")
  ```
  Fungsi internal `torch.load()` memproses berkas biner tersebut secara otomatis di latar belakang. Proses ini mengeksekusi shellcode yang membuka koneksi meterpreter balik (*reverse shell*) ke alamat IP Command and Control (C2), memberikan akses penuh ke mesin developer atau pod kluster training GPU korporat.
* **Tindakan Mitigasi Global:** Hugging Face merespons dengan mewajibkan pemindaian statis terpusat pada setiap berkas yang diunggah, meluncurkan visualisasi badge status keamanan berkas, serta menjadikan format **SafeTensors** sebagai standar *default* untuk seluruh artefak bobot model baru.

---

## 18. Quiz Pemahaman & Challenge

### Pertanyaan Evaluasi

1. **Mengapa inspeksi visual manual terhadap dataset citra atau teks pada Clean-Label Poisoning gagal mengidentifikasi manipulasi data?**
   * A. Karena label sengaja dihapus dari dataset.
   * B. Karena label diubah menjadi kelas acak (*random noise*).
   * C. Karena sampel masukan tampak normal dan berlabel benar secara semantik, namun representasi fiturnya di ruang laten telah didekatkan ke sampel target via optimasi adversarial.
   * D. Karena serangan hanya terjadi pada layer komputasi GPU, bukan pada data mentah.

2. **Apa yang menyebabkan format `.safetensors` secara fundamental kebal terhadap Arbitrary Code Execution jika dibandingkan dengan berkas `.pt` PyTorch standar?**
   * A. SafeTensors menggunakan algoritma enkripsi AES-256 pada bobotnya.
   * B. SafeTensors tidak menggunakan mesin berbasis instruksi tumpukan seperti Pickle Virtual Machine; format ini murni mendefinisikan kamus header JSON dan buffer byte array mentah.
   * C. SafeTensors hanya dapat dibaca oleh bahasa pemrograman Rust, sehingga Python tidak dapat mengeksekusinya.
   * D. SafeTensors memvalidasi seluruh signature hash langsung ke server Hugging Face sebelum memuat file.

3. **Perhatikan opcode PVM berikut:**
   ```text
   cposix\nsystem\n(S'id'\ntR.
   ```
   **Opcode manakah yang secara langsung bertanggung jawab mengeksekusi instruksi sistem `id`?**
   * A. `c` (GLOBAL)
   * B. `S` (STRING)
   * C. `t` (TUPLE)
   * D. `R` (REDUCE)

4. **Metode pertahanan apa yang paling tepat untuk mendeteksi *Neural Trojans* pada model pra-latih jika penyerang tidak membagikan dataset pelatihan aslinya?**
   * A. Neural Cleanse (Reverse-engineering trigger pattern via optimization).
   * B. Validasi checksum MD5.
   * C. Re-training dari awal (*from scratch*).
   * D. Menghapus layer klasifikasi terakhir tanpa fine-tuning.

### Practical Challenge
**Skenario:** Anda bertindak sebagai AI Red Teamer yang bertugas mengaudit sistem inferensi otomatis di sebuah bank. Sistem menggunakan pustaka internal yang memuat checkpoint dari direktori `/opt/models/` menggunakan fungsi warisan PyTorch. 

**Tugas:** Tulis sebuah skrip Python mandiri (`verify_pipeline.py`) tanpa dependensi eksternal selain pustaka standar (`pickletools`, `pathlib`) yang memvalidasi direktori model secara rekursif. Skrip harus mengembalikan kode status kegagalan `sys.exit(1)` jika menemukan berkas `.pt` atau `.bin` yang memuat opcode `REDUCE`, `INST`, atau `BUILD`, dan memberikan laporan detail posisi byte serta nama opcode yang ditemukan.

---

## 19. Summary & Key Takeaways

* Kategori ancaman *Data Poisoning* dan *Supply Chain Backdoors* mengeksploitasi ketergantungan model machine learning modern pada transfer learning dan dataset publik berskala masif.
* *Clean-label targeted poisoning* memanipulasi *decision boundary* model tanpa merusak label data, mengecoh mekanisme auditing dataset konvensional melalui *feature collision* matematis.
* *Neural Trojans* membentuk pemetaan bersyarat yang dorman; model beroperasi dengan performa tinggi pada metrik validasi standar namun menghasilkan deviasi fatal ketika terpapar pemicu (*trigger*).
* Serialisasi model PyTorch berbasis *pickle* mengandung kelemahan arsitektur fundamental yang memungkinkan eksekusi kode arbitrer (*Arbitrary Code Execution*) melalui primitif PVM seperti `__reduce__`.
* Format **SafeTensors** adalah solusi standar industri untuk mengeliminasi risiko eksekusi kode deserialisasi dengan membatasi penyimpanan hanya pada raw tensor buffers dan metadata JSON.
* Integritas model tingkat enterprise harus ditegakkan melalui kombinasi inspeksi statis bytecode, sanitasi data berbasis representasi laten spektral, dan penandatanganan kriptografis (*model signing*) pada pipeline CI/CD.

---

## 20. Referensi Resmi & Standar Keamanan

* **OWASP Top 10 for Large Language Models & GenAI:**
  * LLM03: Supply Chain Vulnerabilities
  * LLM04: Data and Model Poisoning
* **OWASP Machine Learning Security Top 10:**
  * ML02: Data Poisoning Attack
  * ML06: AI Supply Chain Attacks
* **MITRE ATLAS (Adversarial Threat Landscape for Artificial-Intelligence Systems):**
  * AML.T0018: Backdoor ML Model
  * AML.T0020: Poison Training Data
  * AML.T0010: ML Supply Chain Compromise
  * AML.T0017: Exploit ML Artifact Deserialization
* **NIST AI Risk Management Framework (AI RMF 1.0):**
  * NIST AI 100-1: Section 5.2 — *Data Integrity and Provenance in Machine Learning*
* **Hugging Face Security Documentation:**
  * SafeTensors Design Specification: `https://github.com/huggingface/safetensors`
* **Python Software Foundation Security Advisories:**
  * Standard Library `pickle` Risk Architecture: `https://docs.python.org/3/library/pickle.html`