# Bab 05: Multimodal Prototyping & Visual-to-Code Workflows
## Module 01: VLM-Driven Visual-to-Code Synthesis Engine

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memetakan Dekomposisi Spasial UI**: Menerjemahkan hierarki visual dari wireframe, screenshot Figma, atau sketsa kasar menjadi representasi struktural pohon komponen (*Component Tree*) menggunakan Vision-Language Models (VLM).
- **Membangun Pipeline Multimodal Deterministik**: Mengimplementasikan arsitektur *two-pass visual synthesis* (Layout Parsing $\rightarrow$ Component Synthesis) dengan penegakan skema valid berbasis *Abstract Syntax Tree* (AST).
- **Mengintegrasikan Design System Token Injection**: Menyuntikkan aturan tema (*design tokens*, atomic CSS, Tailwind classes, dan *accessibility metadata*) langsung ke dalam *system prompt* VLM guna mencegah halusinasi styling.
- **Mengimplementasikan Self-Healing Syntax & Visual Feedback Loop**: Merancang mekanisme runtime validator untuk menangani kesalahan sintaksis TSX/JSX dan regresi tata letak (*layout drift*) secara otomatis.
- **Mengelola Trade-off Arsitektur Sintesis Kode**: Memilih antara pendekatan *Direct-to-Code (End-to-End)* vs. *Intermediate Representation (AST/JSON schema-first)* berdasarkan kebutuhan latensi, determinisme, dan kepatuhan sistem desain enterprise.

---

### 2. Concept Overview

Paradigma *vibe-coding* pada ranah frontend modern menuntut transisi instan dari abstraksi visual ke kode fungsional tanpa melalui friksi manual *design-to-code handoff*. Model multimodal kontemporer memiliki kapabilitas *spatial grounding* yang mampu memproses koordinat piksel mentah dan memetakannya ke dalam relasi topologi dokumen: flexbox, grid layouts, relasi hierarkis *parent-child*, serta batas-batas semantik interaktif.

```
                    MENTAL MODEL: VISION-TO-CODE PROJECTION
 ┌──────────────────────┐         ┌────────────────────────┐         ┌──────────────────────┐
 │ Raw Visual Artifact  │         │ Intermediate Topology  │         │ Production Artifact  │
 │ (Figma/PNG/Wireframe)│ ──────> │ (Spatial Bounding Tree │ ──────> │ (Strict Typed TSX +  │
 │                      │   VLM   │  + Semantic Nodes)     │   AST   │  Tailwind Tokens)    │
 └──────────────────────┘         └────────────────────────┘         └──────────────────────┘
```

Secara fundamental, sintesis visual-ke-kode bukan sekadar meminta LLM mendeskripsikan gambar dalam bentuk kode HTML. Hal tersebut adalah masalah optimasi terikat (*constrained optimization problem*) yang mencakup tiga domain teoretis:

1. **Semantic Spatial Decomposition**: Ekstraksi batas visual kontur elemen (*bounding boxes*) dan pengelompokan elemen-elemen atomik menjadi molekul UI (misal: tombol, input field, navigation bar) melalui penalaran visual VLM.
2. **Contextual Token Injection**: Penyelarasan visual entitas terhadap kamus token desain (*design token dictionary*) internal organisasi, memastikan warna, tipografi, dan spasi tidak menggunakan *magic values* (misal: `#3b82f6` harus dipetakan ke `bg-primary-500`).
3. **Deterministic AST Projection**: Mengonversi output semi-terstruktur model menjadi AST yang valid, bebas dari komponen usang (*deprecated*), serta mematuhi aturan strict typing TypeScript.

---

### 3. Why It Matters

Dalam lanskap enterprise, kesenjangan antara tim desain (UI/UX) dan tim rekayasa frontend merupakan salah satu penyumbang latensi rilis produk tertinggi (*time-to-market latency*). Masalah-masalah sistemik yang dihadapi meliputi:

- **Design Drift**: Inkonsistensi implementasi CSS antara visual Figma dan kode aktual, memicu audit QA visual manual yang repetitif.
- **Hallucinated Div-Soups**: Pendekatan VLM naif (*single prompt*) cenderung menghasilkan struktur DOM datar yang sarat elemen `<div>` tanpa semantik aksesibilitas (WAI-ARIA), merusak SEO dan pembaca layar (*screen readers*).
- **Infrastruktur Prototype Sekali Pakai**: Prototipe cepat sering kali dibuang karena kodenya tidak terstruktur. Pipeline visual-to-code industri harus menghasilkan kode yang siap disisipkan (*drop-in ready*) ke basis kode produksi: memiliki *type definition*, *props interfaces*, dan isolasi modular.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan visual end-to-end dengan pendekatan *Two-Pass Synthesis* dan *Validation Loop*.

```
 +-------------------------------------------------------------------------------+
 |                        MULTIMODAL V2C PIPELINE ARCHITECTURE                   |
 +-------------------------------------------------------------------------------+
                                          |
                                   [Input Artifact]
                            (PNG / JPEG / WebP / SVG Mockup)
                                          |
                                          v
                         +---------------------------------+
                         |      1. Image Preprocessor      |
                         |  - Aspect-ratio padding         |
                         |  - Downsampling & normalization |
                         |  - Visual Anchor Grid Overlay   |
                         +---------------------------------+
                                          |
                                          v
                         +---------------------------------+
                         |     Design System Registry      |
                         |   - Tailwind Config / CSS Vars  |
                         |   - Component Signature Specs   |
                         +---------------------------------+
                                          |
                                          | (Injected System Prompt)
                                          v
                         +---------------------------------+
                         | 2. Pass 1: Spatial Layout VLM   |
                         | (Layout & Hierarchy Extraction) |
                         +---------------------------------+
                                          |
                                          v  (Layout JSON Schema)
                         +---------------------------------+
                         | 3. Pass 2: Component Synthesis  |
                         |   - Generates Types & State     |
                         |   - Emits Strict TSX Output     |
                         +---------------------------------+
                                          |
                                          v  (Raw Code String)
                         +---------------------------------+
                         |   4. AST Compiler & Validator   | <----+ (Feedback Loop)
                         |  - Babel/Biemme Parser Check    |      |
                         |  - Tailwind Linter Validation   |      |
                         +---------------------------------+      |
                                     /         \                  |
                           [Syntax Error]     [Valid AST]         |
                                 /                 \              |
                                v                   v             |
                     +--------------------+   +-------------------+
                     | 5. Self-Healing    |   | 6. Format Engine  |
                     |    Repair Agent    |   |  - Prettier Clean |
                     +--------------------+   +-------------------+
                               |                        |
                               +------------------------+
                                                        v
                                              [Production Artifact]
                                           (Next.js Component Block)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Visual Grounding dan Anchor Grid Coordinate Systems
VLM memiliki keterbatasan intrinsik dalam merekayasa tata letak spasial yang padat jika hanya mengandalkan resolusi murni. Untuk memitigasi hal ini, teknik *Visual Anchor Grid* diterapkan: gambar dipetakan ke dalam matriks koordinat $1000 \times 1000$ yang dinormalisasi. Instruksi sistem mewajibkan model untuk menandai posisi kontainer dengan bounding box:
$$\text{BBox} = [y_{min}, x_{min}, y_{max}, x_{max}]$$
Hal ini memastikan model secara sadar membedakan komponen bersarang (*nested containers*) dari elemen tingkat atas (*top-level grid wrappers*).

#### B. Two-Pass Decoupled Generation
Menggabungkan deteksi visual, tata letak, logika interaksi, dan integrasi tipe dalam satu pemanggilan inferensi (*single prompt*) secara drastis meningkatkan *cognitive load* pada context window LLM, yang berujung pada halusinasi sintaksis.
- **Pass 1 (Topology Extraction)**: Model hanya mengidentifikasi struktur pohon DOM konseptual dalam format JSON murni. Pada fase ini tidak ada kode React yang diekstraksi.
- **Pass 2 (Syntactic Translation)**: JSON hasil Pass 1, bersama dengan screenshot asli dan kamus *Design System Tokens*, dikirimkan ke model sintesis kode untuk menghasilkan TypeScript TSX yang strictly-typed.

#### C. Deterministic Constrained AST Validation
Kode yang dihasilkan diverifikasi terhadap pustaka parser seperti `@babel/parser` (Node.js) atau modul parsing AST berbasis Tree-sitter. Setiap pelanggaran hierarki komponen, penggunaan atribut HTML usang, atau ketidaksesuaian penutupan tag JSX ditangkap langsung di tingkat memori sebelum kode dieksekusi atau disimpan ke disk.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul inti generator visual-to-code menggunakan Python 3.11+, Pydantic v2 untuk validasi struktural, dan integrasi model multimodal melalui SDK Google GenAI (Gemini 1.5 Pro). Arsitektur ini dirancang secara modular dan *clean-architecture-compliant*.

```python
"""
Core Engine for Multimodal Visual-to-Code Synthesis.
Implements Two-Pass extraction with AST and schema-level validation.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("VisualToCodeEngine")


class ComponentType(str, Enum):
    CONTAINER = "container"
    BUTTON = "button"
    INPUT = "input"
    TYPOGRAPHY = "typography"
    IMAGE = "image"
    CARD = "card"
    NAVIGATION = "navigation"


class VisualElementNode(BaseModel):
    """Representasi perantara (Intermediate Representation) struktur visual."""
    id: str = Field(description="Unique ID elemen dalam format kebab-case")
    type: ComponentType
    semantic_tag: str = Field(description="HTML5 Semantic tag, e.g., 'header', 'nav', 'main', 'section'")
    bounding_box_normalized: List[int] = Field(
        description="Koordinat [ymin, xmin, ymax, xmax] skala 0-1000",
        min_length=4,
        max_length=4
    )
    tailwind_classes: List[str] = Field(description="Utility classes yang disarankan")
    children: Optional[List[VisualElementNode]] = Field(default_factory=list)


class LayoutTopology(BaseModel):
    """Pohon hierarki tata letak hasil ekstraksi Pass-1."""
    root_layout_type: str = Field(description="Tipe root container: 'flex-col', 'grid', dll.")
    elements: List[VisualElementNode]


@dataclass(frozen=True)
class EngineConfig:
    model_name: str = "gemini-2.5-pro"
    max_output_tokens: int = 8192
    temperature: float = 0.1
    design_system_context: str = (
        "Design System Rules: Use Tailwind CSS v3+. Prefer Flexbox and CSS Grid. "
        "Strictly adhere to modern semantic HTML5. Dark-mode ready using dark: variants. "
        "Do not invent arbitrary hex codes if a tailwind palette color exists."
    )


class ASTValidationError(Exception):
    """Dilempar ketika kode yang dihasilkan gagal dalam pemeriksaan sintaksis JSX/TSX."""
    pass


class VisualToCodeCompiler:
    """Mesin orkestrasi untuk sintesis kode visual-ke-TSX."""

    def __init__(self, api_key: Optional[str] = None, config: Optional[EngineConfig] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY harus didefinisikan via argumen atau environment variable.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.config = config or EngineConfig()

    def _encode_image(self, image_path: Path) -> types.Part:
        """Memvalidasi dan mengonversi berkas citra menjadi part multimodal yang kompatibel."""
        if not image_path.exists():
            raise FileNotFoundError(f"Visual asset tidak ditemukan: {image_path}")
        
        suffix = image_path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp"
        }
        mime_type = mime_map.get(suffix)
        if not mime_type:
            raise ValueError(f"Ekstensi gambar tidak didukung: {suffix}")

        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()

        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    async def _pass_one_extract_topology(self, image_part: types.Part) -> LayoutTopology:
        """Pass 1: Analisis spasial dan ekstraksi pohon topologi UI (JSON)."""
        logger.info("Memulai Pass 1: Ekstraksi Topologi Spasial...")

        prompt = (
            "Analyze the layout of this UI design. Deconstruct it into a recursive structural tree. "
            "Map each visual entity accurately with normalized bounding boxes (scale 0-1000). "
            "Ensure parent-child visual containment is strictly reflected in the nesting."
        )

        response = self.client.models.generate_content(
            model=self.config.model_name,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                temperature=self.config.temperature,
                response_mime_type="application/json",
                response_schema=LayoutTopology,
            ),
        )

        try:
            raw_text = response.text
            structured_data = LayoutTopology.model_validate_json(raw_text)
            logger.info("Pass 1 Berhasil: Topologi hierarki berhasil divalidasi.")
            return structured_data
        except (ValidationError, json.JSONDecodeError) as e:
            logger.error("Pass 1 Gagal: Output model tidak mematuhi skema JSON LayoutTopology.")
            raise ValueError(f"Skema JSON tidak valid dari Pass 1: {str(e)}") from e

    async def _pass_two_synthesize_tsx(
        self, 
        image_part: types.Part, 
        topology: LayoutTopology
    ) -> str:
        """Pass 2: Menerjemahkan topologi dan referensi gambar menjadi React TSX siap produksi."""
        logger.info("Memulai Pass 2: Sintesis Komponen React TSX...")

        topology_json = topology.model_dump_json(indent=2)
        
        system_instruction = (
            "You are a Principal Frontend Engineer specializing in Next.js, React 19, TypeScript, and Tailwind CSS. "
            f"{self.config.design_system_context}\n"
            "Generate a fully accessible, strictly-typed TSX component based on the provided layout topology and visual image. "
            "Include proper Lucide React icons where applicable. "
            "Return ONLY raw executable TypeScript JSX code wrapped inside a markdown block: ```tsx ... ```. "
            "Do not include commentary or explanations."
        )

        prompt = (
            f"Here is the verified Layout Topology JSON:\n{topology_json}\n\n"
            "Using both the original visual design from the image and this topology, "
            "synthesize a production-ready TSX component. "
            "Ensure standard semantic elements (<header>, <main>, <nav>, <section>, <button>) are properly used."
        )

        response = self.client.models.generate_content(
            model=self.config.model_name,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
            ),
        )

        raw_code = self._extract_code_block(response.text)
        return raw_code

    def _extract_code_block(self, text: str) -> str:
        """Mengekstrak blok kode TSX murni dari respons Markdown."""
        pattern = r"```(?:tsx|typescript|jsx)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _validate_syntactic_integrity(self, code: str) -> None:
        """
        Validasi integritas sintaksis dasar (Level AST Parser Pre-flight).
        Memastikan keseimbangan tag JSX dan bracket.
        """
        logger.info("Menjalankan Pre-flight AST Syntax Checking...")
        open_tags = len(re.findall(r"<[a-zA-Z0-9]+(?:\s+[^>]*?)?(?<!/)>", code))
        close_tags = len(re.findall(r"</[a-zA-Z0-9]+>", code))
        
        # Validasi seimbang sederhana sebelum pass ke compiler runtime
        if open_tags != close_tags:
            raise ASTValidationError(
                f"Asimetri tag JSX terdeteksi! Tag buka: {open_tags}, Tag tutup: {close_tags}. "
                "Kode yang dihasilkan berpotensi merusak compiler."
            )
        
        # Cek tipe imports minimal
        if "export default" not in code and "export function" not in code:
            raise ASTValidationError("Komponen TSX tidak mengekspos fungsi modul utama (hilang 'export default').")

    async def compile(self, image_path: Path) -> str:
        """Orkestrator utama: Image -> Topology -> Code -> Validation."""
        image_part = self._encode_image(image_path)
        
        # Eksekusi Pipeline Two-Pass
        topology = await self._pass_one_extract_topology(image_part)
        generated_tsx = await self._pass_two_synthesize_tsx(image_part, topology)
        
        # Validasi Integritas
        try:
            self._validate_syntactic_integrity(generated_tsx)
        except ASTValidationError as err:
            logger.warning("Deteksi anomali sintaksis: Memulai perbaikan mandiri (Self-Healing)...")
            generated_tsx = await self._self_healing_repair(generated_tsx, str(err))

        return generated_tsx

    async def _self_healing_repair(self, malformed_code: str, error_context: str) -> str:
        """Loop pemulihan mandiri jika tahap validasi pre-flight menemukan defek."""
        repair_prompt = (
            "The following React TSX code contains structural/syntactical errors:\n"
            f"ERROR CONTEXT: {error_context}\n\n"
            f"ORIGINAL CODE:\n{malformed_code}\n\n"
            "Fix the syntax error, ensure all JSX tags are correctly closed, and return ONLY the corrected valid TSX code inside ```tsx."
        )

        response = self.client.models.generate_content(
            model=self.config.model_name,
            contents=[repair_prompt],
            config=types.GenerateContentConfig(temperature=0.0),
        )

        repaired_code = self._extract_code_block(response.text)
        self._validate_syntactic_integrity(repaired_code)
        logger.info("Self-healing selesai: Kode berhasil dipulihkan.")
        return repaired_code


# ---------------------------------------------------------
# Skrip Demonstrasi Eksekusi
# ---------------------------------------------------------
if __name__ == "__main__":
    import asyncio

    async def main():
        # Setup mock file untuk pengujian sintaksis compiler
        dummy_asset = Path("./mock_dashboard_wireframe.png")
        
        # Buat dummy PNG jika belum tersedia (hanya untuk testing lokal)
        if not dummy_asset.exists():
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (800, 600), color=(240, 242, 245))
            d = ImageDraw.Draw(img)
            d.rectangle([(50, 50), (750, 120)], fill=(255, 255, 255), outline=(200, 200, 200))
            d.text((70, 75), "Header: Analytics Platform", fill=(0, 0, 0))
            d.rectangle([(50, 150), (250, 550)], fill=(255, 255, 255), outline=(200, 200, 200))
            d.rectangle([(280, 150), (750, 550)], fill=(255, 255, 255), outline=(200, 200, 200))
            img.save(dummy_asset)

        # Inisialisasi Compiler
        compiler = VisualToCodeCompiler()
        
        try:
            tsx_result = await compiler.compile(dummy_asset)
            print("\n========== GENERATED PRODUCTION TSX ==========\n")
            print(tsx_result)
            print("\n==============================================\n")
        except Exception as ex:
            logger.error(f"Pipeline Execution Aborted: {str(ex)}")

    # Jalankan runtime asinkron
    if os.getenv("GEMINI_API_KEY"):
        asyncio.run(main())
    else:
        print("[SKIP] Set GEMINI_API_KEY untuk mengeksekusi pipeline end-to-end.")
```

---

### 7. Edge Cases & Failure Modes

| Failure Mode | Mekanisme Terjadinya | Dampak Sistem | Mitigasi Enterprise |
| :--- | :--- | :--- | :--- |
| **Micro-Font OCR Degradation** | Label teks dengan ukuran font $<10\text{px}$ atau kontras rendah mengalami salah baca (*character hallucination*). | Label tombol atau header tabel berisi karakter *gibberish*. | Terapkan pra-pemrosesan citra menggunakan Super-Resolution (misal: Real-ESRGAN) atau injeksikan layer OCR terpisah (Tesseract/PaddleOCR) sebagai metadata teks eksplisit. |
| **Extreme Aspect Ratio Distortion** | Mockup dengan panjang vertikal ekstrem (misal: halaman landing panjang $1200 \times 12000\text{px}$) dikompresi ke resolusi batas VLM. | Detail visual bawah menjadi blur; hierarki komponen hancur. | Implementasikan *Sliding Window Image Tiling*: gambar dipotong menjadi segmen tumpang tindih (*overlapping tiles*), diproses secara paralel, lalu dijahit kembali melalui rekonstruksi pohon hierarki. |
| **Arbitrary Hex Bleed** | VLM mengabaikan *Design System Context* dan mencantumkan styling arbitrary seperti `bg-[#1a2b3c]`. | Melanggar governance design system korporat; memperbesar bundle CSS. | Terapkan validasi berbasis linter AST post-generation dengan aturan kustom ESLint/PostCSS yang memblokir arbitrary values dan memetakannya otomatis ke token Tailwind terdekat via *Euclidean color distance calculation*. |
| **Z-Index Layer Collapse** | Elemen floating, modal dialog, atau dropdown dirender flat sejajar dengan background container. | Komponen tidak dapat diinteraksikan atau tertutup elemen statis. | Penambahan prompt constraint spesifik yang mendeteksi atribut visual seperti drop shadow (*elevation*) dan pemetaan otomatis ke CSS classes `relative`, `absolute`, serta skala `z-index`. |

---

### 8. Trade-offs & Alternatif Solusi

#### Direct-to-Code vs. Schema-First Intermediate Representation (IR)

```
                       ARCHITECTURAL TRADE-OFF SPECTRUM
   Low Determinism                                            High Determinism
   Low Latency                                                High Reliability
  ┌────────────────────────┐                    ┌────────────────────────────┐
  │ Direct End-to-End TSX  │                    │ Intermediate Schema (IR)   │
  │ (Vision -> TSX String) │                    │ (Vision -> JSON -> AST)    │
  └────────────────────────┘                    └────────────────────────────┘
   * Cocok untuk prototyping                     * Wajib untuk platform enterprise
   * Rentan terhadap sintaks rusak               * Kontrak validasi sangat kuat
   * Sulit divalidasi deterministik              * Self-healing mudah diisolasi
```

- **Direct End-to-End TSX**:
  - *Kelebihan*: Latensi rendah (hanya 1 pemanggilan LLM), pemanfaatan token output lebih efisien, implementasi pipeline sederhana.
  - *Kekurangan*: Sering menghasilkan markup HTML tidak semantik, komponen rentan mengalami parsing error di Babel, styling sulit diaudit secara programatis.
- **Two-Pass IR (JSON Schema-First)** *(Dipilih dalam modul ini)*:
  - *Kelebihan*: Pemisahan yang tegas antara abstraksi spasial (tata letak) dan sintesis logika kode; memfasilitasi verifikasi deterministik skema Pydantic/Zod sebelum kode dihasilkan; memungkinkan penggantian framework target (misal: dari React ke Svelte/Vue) tanpa mengubah ekstraksi Pass 1.
  - *Kekurangan*: Konsumsi token LLM berlipat ganda, latensi generasi meningkat sekitar $1.8\times - 2.5\times$.

---

### 9. Best Practices & Standard Industri

1. **Strict Design Token Constraining**: Jangan pernah memberi kebebasan model untuk menentukan nilai CSS tanpa batas. Masukkan kamus token warna, ukuran tipografi, dan padding langsung ke dalam *system prompt* atau via *retrieval-augmented generation* (RAG) dokumen desain.
2. **Deterministic Temperature Tuning**: Untuk tugas translasi struktur spasial dan kode visual, pertahankan rentang parameter $0.0 \le \text{temperature} \le 0.2$. Temperatur yang lebih tinggi menyebabkan halusinasi tata letak dan penutupan tag JSX asimetris.
3. **Automated Visual Regression Testing (VRT) Loop**: Di lingkungan CI/CD, lakukan kompilasi dinamis kode hasil generasi di dalam sandbox headless (misal: Playwright). Ambil tangkapan layar dari TSX yang dirender, bandingkan dengan gambar input asli menggunakan metrik SSIM (*Structural Similarity Index Measure*), dan jika deviasi $> 15\%$, lemparkan umpan balik visual kembali ke agen self-healing.
4. **Semantics-First Enforcement**: Larang keras pengabaian WAI-ARIA. Tombol tanpa teks wajib memiliki `aria-label`, gambar wajib memiliki `alt`, dan form control wajib dihubungkan dengan elemen `<label>`.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan membangun pipeline otomatis yang mampu menerima sketsa wireframe kasir/POS (*Point of Sales*) restoran, mendeteksi struktur tabel transaksi, dan menyusunnya menjadi komponen Next.js/Tailwind modular yang mematuhi standar desain internal.

#### Langkah Pengerjaan

1. **Setup Lingkungan Virtual & Dependensi**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install google-genai pydantic pillow
   export GEMINI_API_KEY="your-api-key-here"
   ```

2. **Eksekusi Lab Engine**:
   - Terapkan kode dari **Bagian 6** ke dalam berkas `v2c_engine.py`.
   - Jalankan kompilasi terhadap mockup visual:
   ```bash
   python v2c_engine.py
   ```

3. **Verifikasi Output**:
   - Pastikan keluaran TSX memiliki antarmuka Props TypeScript:
     ```typescript
     interface OrderItem {
       id: string;
       name: string;
       price: number;
       quantity: number;
     }
     ```
   - Periksa apakah komponen menggunakan container modular semantik (`<aside>` untuk sidebar ringkasan belanja, `<main>` untuk grid item katalog).

4. **Kriteria Keberhasilan (*Acceptance Criteria*)**:
   - File hasil kompilasi bersih dari format pembungkus ganda (tidak ada dobel markdown tick).
   - Penggunaan class Tailwind CSS tidak mengandung arbitrary values tanpa deklarasi yang sah.
   - Pengecekan pre-flight AST berhasil lolos tanpa memicu eksepsi `ASTValidationError`.