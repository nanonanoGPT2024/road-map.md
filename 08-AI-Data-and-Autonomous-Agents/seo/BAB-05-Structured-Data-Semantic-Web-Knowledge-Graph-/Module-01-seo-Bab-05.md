# Bab 05: Structured Data, Semantic Web & Knowledge Graph Engineering (Module 01)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memodelkan Entitas Enterprise**: Mentransformasikan data relasional dan dokumen semi-terstruktur menjadi representasi ontologi formal berbasis standar W3C (RDF, RDFS, OWL) dan Schema.org vocabulary.
- **Mengarsitekturi Dynamic Knowledge Graph Pipeline**: Membangun pipeline ekstraksi, rekonsiliasi, dan resolusi entitas (*Entity Disambiguation*) otomatis yang menghubungkan entitas internal dengan basis pengetahuan publik (Wikidata, DBpedia).
- **Mengimplementasikan Serialisasi `@graph` JSON-LD Skala Produksi**: Membangun payload JSON-LD tingkat lanjut menggunakan topologi multi-node yang saling terhubung (*interconnected entity graphs*) bebas dari anomali fragmentasi node.
- **Mengintegrasikan Graph-Augmented SEO Engine**: Mengoptimalkan retrieval semantic search engine dan LLM web crawlers (Google Gemini, OpenAI SearchBot, Perplexity) melalui injeksi metadata deterministik dan validasi SHACL (*Shapes Constraint Language*).
- **Mengeksekusi Entity Reconciliation Heuristics**: Mengembangkan algoritma pencocokan entitas berbasis jarak leksikal, analisis kontekstual, dan penelusuran graf relasional guna mencegah fenomena kanonikalisasi yang salah (*entity drift/aliasing*).

---

## 2. Concept Overview

Evolusi web dari era leksikal (pencocokan string dan frekuensi kata kunci TF-IDF) menuju era semantik (pemahaman makna entitas dan relasi) mengubah paradigma optimasi mesin pencari secara fundamental. Search engine modern tidak lagi mengindeks dokumen semata; mereka memetakan realitas objektif ke dalam **Enterprise Knowledge Graph (EKG)**.

```
       [Dokumen Web Tradisional]                     [Web Semantik Modern]
+------------------------------------+      +------------------------------------+
|  "Google didirikan oleh Larry Page |      |  (Entity: Google LLC)              |
|   dan Sergey Brin di California."  | ---> |    --[foundedBy]--> (Larry Page)   |
|                                    |      |    --[foundedBy]--> (Sergey Brin)  |
|  *Indeks: "Google", "Larry", dsb.  |      |    --[location]-->  (California)   |
+------------------------------------+      +------------------------------------+
```

### Mental Model: Web sebagai Distributed Property Graph
Sebuah dokumen web bukan lagi sekadar kumpulan blok teks HTML, melainkan sekumpulan klaim (*assertions*) faktual. Setiap klaim direpresentasikan dalam bentuk **Resource Description Framework (RDF) Triple**:

$$\text{Triple} = \langle \text{Subject}, \text{Predicate}, \text{Object} \rangle$$

Di mana:
- **Subject ($S$)**: URI yang merepresentasikan entitas unik (misal: `https://example.com/id/org/tech-corp`).
- **Predicate ($P$)**: Properti atau relasi terdefinisi dari ontologi (misal: `schema:founder`).
- **Object ($O$)**: Nilai literal (string, tanggal, angka) atau URI entitas lain (misal: `https://wikidata.org/wiki/Q92`).

### Jembatan Menuju AI Search Engines
Mesin pencari berbasis Retrieval-Augmented Generation (RAG) dan AI Agents mengonsumsi halaman web melalui kombinasi web scraping dan graph parsing. Ketika website menyediakan struktur semantik yang eksplisit melalui JSON-LD dengan skema `@graph`:
1. **Parser deterministik** mesin pencari tidak perlu menebak batas entitas (*entity boundary detection*) melalui pemrosesan NLP yang rentan halusinasi.
2. **Confidence score** pengenalan entitas meningkat ke ambang batas maksimum, membuka fitur SERP khusus (Knowledge Panel, Sitelinks Searchbox, Carousels, Rich Cards).
3. Entitas web Anda terdaftar sebagai *authoritative source node* pada graf global, menjadikannya referensi factual grounding bagi LLM.

---

## 3. Why It Matters

### Masalah di Dunia Nyata
Dalam sistem e-commerce berskala jutaan SKU atau platform publikasi enterprise, pendekatan penandaan terisolasi (*fragmented structured data*) sering kali menyebabkan kegagalan interpretasi:
- **Entity Ambiguity**: Dua produk dengan nama sama diperlakukan sebagai satu entitas identik, atau satu brand dengan cabang internasional dianggap entitas yang saling bersaing (*cannibalization*).
- **Orphan Nodes**: Penambahan blok `<script type="application/ld+json">` terpisah untuk `BreadcrumbList`, `Product`, dan `Organization` tanpa relasi eksplisit menciptakan entitas yatim piatu (*orphan entities*) yang gagal diabstraksikan oleh parser Googlebot.
- **Zero-Click Searches & SGE Displacement**: Kehadiran *AI Overviews* memangkas lalu lintas organik tradisional. Website yang tidak menyediakan representasi relasional faktual tidak akan diikutsertakan sebagai sumber rujukan utama dalam sintesis jawaban mesin AI.

### Kebutuhan Enterprise
1. **Unified Semantic Topology**: Menghubungkan metadata katalog produk, profil korporat, penulis artikel, dan ulasan pelanggan ke dalam satu kesatuan graf deterministik.
2. **Algorithmic Disambiguation**: Penggunaan `sameAs` referencing yang mengarah secara deterministik ke Knowledge Bases otoritatif seperti Wikidata, VIAF, Crunchbase, dan LinkedIn.
3. **Resilience to Algorithmic Updates**: Website yang fondasinya berorientasi pada entitas (*entity-first SEO*) memiliki ketahanan jauh lebih tinggi terhadap pembaruan inti algoritma (*Core Updates*) karena reputasinya terikat pada kredibilitas entitas (E-E-A-T) yang tervalidasi pada Google Knowledge Graph.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur end-to-end pemrosesan data internal aplikasi menjadi Knowledge Graph terdistribusi yang dikonsumsi oleh web crawler dan AI agent:

```
[ CMS / Database / PIM ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│      Entity Extraction & Normalization Service         │
│  - Text Chunking & Entity Boundary Detection           │
│  - Schema.org Attribute Mapping                        │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│           Entity Reconciliation Engine                 │
│  - Internal Canonical ID Resolution                    │
│  - External Authority Linking (Wikidata / DBpedia)     │
│  - Semantic Deduplication (String Jaro-Winkler + Cos)  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│          Knowledge Graph Assembler (@graph)            │
│  - Node Interlinking (Cross-referencing @id values)    │
│  - Schema Validation Engine (SHACL / Pydantic Rules)   │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌─────────────────────────┐ ┌────────────────────────────┐
│ Edge Cache Injection    │ │ Internal Semantic Store    │
│ (Dynamic JSON-LD SSR)   │ │ (GraphDB / RDF Triplestore)│
└────────────┬────────────┘ └────────────────────────────┘
             │
             ▼
[ Web Crawlers / AI Retrieval Engines ]
  (Googlebot, SearchBot, Perplexity)
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Graph Topology Menggunakan Sintaks `@graph`
Bentuk implementasi JSON-LD standar sering kali membuat pohon terpisah untuk setiap komponen:
```json
// ANTI-PATTERN: Entitas terfragmentasi
{"@context": "https://schema.org", "@type": "Product", "name": "Enterprise ERP"}
{"@context": "https://schema.org", "@type": "Organization", "name": "SaaS Vendor"}
```
Pendekatan enterprise mensyaratkan pemanfaatan parameter `@graph`. Seluruh entitas diletakkan sejajar di dalam array `@graph`, lalu saling mereferensikan melalui atribut `@id` yang berfungsi sebagai Uniform Resource Identifier (URI) kanonikal:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://example.com/#organization",
      "name": "SaaS Vendor",
      "url": "https://example.com"
    },
    {
      "@type": "Product",
      "@id": "https://example.com/product/erp/#product",
      "name": "Enterprise ERP",
      "manufacturer": {
        "@id": "https://example.com/#organization"
      }
    }
  ]
]
```

### B. Resolusi dan Penyelarasan Entitas (*Entity Disambiguation*)
Mesin pencari menetapkan entitas berdasarkan kepastian identitas. Properti `sameAs` adalah mekanisme formal untuk menyatakan identitas bahwa dua URI menunjuk pada entitas ontologis yang sama secara matematis ($A \equiv B$).
- **Identifikasi Internal**: Menggunakan pola fragment URI deterministik (misal: `https://example.com/author/john-doe/#person`).
- **Penyelarasan Eksternal**: Memetakan entitas ke *Wikidata QID* (misal: `https://www.wikidata.org/wiki/Q95` untuk Google). Ini memungkinkan search engine mengimpor seluruh *trust score* dan relasi latar belakang dari basis pengetahuan global secara instan.

### C. Validasi Graf Menggunakan Prinsip SHACL
Validasi JSON bukan sekadar validasi tipe data sintaksis (*JSON Schema*), melainkan validasi topologi semantik graf. Melalui *Shapes Constraint Language* (SHACL), arsitek data memastikan bahwa relasi graf mematuhi aturan keterhubungan. Sebagai contoh:
- Setiap instans `Product` **wajib** memiliki referensi ke `Brand` atau `Organization`.
- Setiap instans `Article` **wajib** memiliki `author` yang bertipe `Person` atau `Organization`, di mana `Person` tersebut memiliki properti `sameAs` minimal satu sumber terverifikasi.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi Knowledge Graph Engineering Pipeline dalam Python menggunakan pendekatan Clean Architecture. Modul ini menangani pemodelan entitas, rekonsiliasi ke basis eksternal, validasi semantik deterministik via Pydantic, dan serialisasi ke `@graph` JSON-LD.

```python
"""
Knowledge Graph Engineering Pipeline for Semantic SEO.
Architecture: Clean Architecture / Domain-Driven Design (DDD)
Dependencies: pydantic>=2.0, requests>=2.28.0
"""

from __future__ import annotations
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from pydantic import BaseModel, Field, HttpUrl, ValidationError

# Setup industrial-grade logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("KnowledgeGraphEngine")


# ----------------------------------------------------------------------
# DOMAIN MODELS & SCHEMAS (SHACL-like enforcement using Pydantic V2)
# ----------------------------------------------------------------------

class SemanticNode(BaseModel):
    id: str = Field(..., alias="@id", description="URI representasi kanonikal node")
    type: str = Field(..., alias="@type", description="Schema.org vocabulary type")

    class Config:
        populate_by_name = True


class EntityReference(BaseModel):
    id: str = Field(..., alias="@id")

    class Config:
        populate_by_name = True


class OrganizationNode(SemanticNode):
    type: str = Field(default="Organization", alias="@type")
    name: str = Field(..., min_length=2)
    url: HttpUrl
    sameAs: Optional[List[HttpUrl]] = Field(default_factory=list)


class PersonNode(SemanticNode):
    type: str = Field(default="Person", alias="@type")
    name: str = Field(..., min_length=2)
    worksFor: Optional[EntityReference] = None
    jobTitle: Optional[str] = None
    sameAs: Optional[List[HttpUrl]] = Field(default_factory=list)


class ArticleNode(SemanticNode):
    type: str = Field(default="Article", alias="@type")
    headline: str = Field(..., max_length=110)
    inLanguage: str = Field(default="id-ID")
    author: EntityReference
    publisher: EntityReference
    mainEntityOfPage: HttpUrl


# ----------------------------------------------------------------------
# RECONCILIATION SERVICES
# ----------------------------------------------------------------------

class IEntityReconciler(ABC):
    @abstractmethod
    def resolve_external_id(self, entity_name: str, entity_type: str) -> Optional[str]:
        """Menyelesaikan nama entitas ke URI Knowledge Base Publik (Wikidata)"""
        pass


class MockWikidataReconciler(IEntityReconciler):
    """
    Mock resolver deterministik untuk keperluan enterprise offline testing.
    Pada fase produksi, hubungkan implementasi ini ke SPARQL Endpoint / Wikidata API.
    """
    def __init__(self):
        self._registry = {
            "OpenAI": "https://www.wikidata.org/wiki/Q115049400",
            "Google": "https://www.wikidata.org/wiki/Q95",
            "Microsoft": "https://www.wikidata.org/wiki/Q2283",
        }

    def resolve_external_id(self, entity_name: str, entity_type: str) -> Optional[str]:
        logger.debug(f"Merekonsiliasi entitas '{entity_name}' tipe '{entity_type}'...")
        return self._registry.get(entity_name)


# ----------------------------------------------------------------------
# GRAPH BUILDER CORE
# ----------------------------------------------------------------------

class KnowledgeGraphBuilder:
    def __init__(self, base_uri: str, reconciler: Optional[IEntityReconciler] = None):
        parsed = urlparse(base_uri)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Base URI tidak valid: {base_uri}")
        
        self.base_uri = base_uri.rstrip("/")
        self.reconciler = reconciler or MockWikidataReconciler()
        self._nodes: Dict[str, Dict[str, Any]] = {}

    def _generate_id(self, path: str, fragment: str) -> str:
        clean_path = path.strip("/")
        return f"{self.base_uri}/{clean_path}#{fragment}"

    def register_organization(self, path: str, name: str, url: str) -> EntityReference:
        node_id = self._generate_id(path, "organization")
        same_as = []
        
        external_uri = self.reconciler.resolve_external_id(name, "Organization")
        if external_uri:
            same_as.append(external_uri)

        node = OrganizationNode(
            id=node_id,
            name=name,
            url=url, # type: ignore
            sameAs=same_as # type: ignore
        )
        self._nodes[node_id] = node.model_dump(by_alias=True, exclude_none=True)
        return EntityReference(id=node_id)

    def register_author(self, path: str, name: str, org_ref: Optional[EntityReference] = None, job_title: Optional[str] = None) -> EntityReference:
        node_id = self._generate_id(path, "author")
        node = PersonNode(
            id=node_id,
            name=name,
            worksFor=org_ref,
            jobTitle=job_title
        )
        self._nodes[node_id] = node.model_dump(by_alias=True, exclude_none=True)
        return EntityReference(id=node_id)

    def register_article(
        self,
        path: str,
        headline: str,
        author_ref: EntityReference,
        publisher_ref: EntityReference,
        canonical_url: str
    ) -> EntityReference:
        node_id = self._generate_id(path, "article")

        # Verifikasi referensi integritas graf lokal
        if author_ref.id not in self._nodes:
            raise ValueError(f"Integritas graf gagal: Node Author ID '{author_ref.id}' tidak terdaftar.")
        if publisher_ref.id not in self._nodes:
            raise ValueError(f"Integritas graf gagal: Node Publisher ID '{publisher_ref.id}' tidak terdaftar.")

        node = ArticleNode(
            id=node_id,
            headline=headline,
            author=author_ref,
            publisher=publisher_ref,
            mainEntityOfPage=canonical_url # type: ignore
        )
        self._nodes[node_id] = node.model_dump(by_alias=True, exclude_none=True)
        return EntityReference(id=node_id)

    def serialize_json_ld(self, indent: int = 2) -> str:
        """Menghasilkan representasi payload JSON-LD standar W3C/Google Search."""
        payload = {
            "@context": "https://schema.org",
            "@graph": list(self._nodes.values())
        }
        return json.dumps(payload, indent=indent, ensure_ascii=False)


# ----------------------------------------------------------------------
# EXECUTION DEMO & RUNTIME VERIFICATION
# ----------------------------------------------------------------------

if __name__ == "__main__":
    try:
        BASE_DOMAIN = "https://techcorp.com"
        builder = KnowledgeGraphBuilder(base_uri=BASE_DOMAIN)

        # 1. Daftarkan Organisasi (Penerbit)
        org_ref = builder.register_organization(
            path="/about-us",
            name="OpenAI",  # Akan direkonsiliasi otomatis ke Wikidata
            url="https://techcorp.com"
        )

        # 2. Daftarkan Penulis (Person) yang terhubung ke Organisasi
        author_ref = builder.register_author(
            path="/team/dr-satria",
            name="Dr. Satria W.",
            org_ref=org_ref,
            job_title="Principal AI Architect"
        )

        # 3. Daftarkan Artikel yang menautkan relasi Graph Node
        builder.register_article(
            path="/insights/semantic-search-2026",
            headline="Rekayasa Semantic Web dan Knowledge Graph untuk AI Search Engine",
            author_ref=author_ref,
            publisher_ref=org_ref,
            canonical_url="https://techcorp.com/insights/semantic-search-2026"
        )

        # 4. Serialisasi Graf menjadi JSON-LD
        json_ld_output = builder.serialize_json_ld()
        print("=== PRODUCTION-READY @graph JSON-LD PAYLOAD ===")
        print(json_ld_output)

    except ValidationError as e:
        logger.error(f"Gagal memvalidasi data skema semantik: {e.json()}")
    except Exception as e:
        logger.error(f"Kegagalan sistem internal Knowledge Graph: {str(e)}", exc_info=True)
```

---

## 7. Edge Cases & Failure Modes

### 1. Circular Reference Pitfalls
- **Mekanisme Kegagalan**: Node $A$ (`Author`) mereferensikan Node $B$ (`Organization`) melalui `worksFor`, sementara Node $B$ mereferensikan Node $A$ melalui `founder`. Jika diserialisasi secara naif menggunakan tree serialization (tanpa format `@graph` berbasis `@id`), serialiser akan memicu rekursi tanpa akhir (*infinite recursion/stack overflow*).
- **Mitigasi**: Seluruh relasi antar-node dalam skema JSON-LD wajib dikonversi menjadi representasi *shallow references* berbasis `@id` Pointer Object (`{"@id": "URI"}`), bukan nested inline expansion.

### 2. Entity Disambiguation Drift
- **Mekanisme Kegagalan**: Perusahaan mengaitkan entity `sameAs` ke URI Wikidata yang tidak tepat secara taksonomis. Contoh: Mengaitkan perusahaan privat "Apple Corps" (label musik) dengan "Apple Inc." (perusahaan komputasi). Dampaknya, Google Knowledge Engine mendegradasi trust score domain akibat inkonsistensi atribut.
- **Mitigasi**: Terapkan mekanisme validasi ganda leksikal-kontekstual sebelum menyuntikkan `sameAs`. Cocokkan properti `instance of` (P31) pada Wikidata target dengan `@type` skema internal sebelum di-merge.

### 3. Payload Bloat pada DOM Parsing
- **Mekanisme Kegagalan**: Memuat grafik pengetahuan relasional yang terlalu masif (misal: menghubungkan seluruh katalog ratusan produk terkait langsung ke dalam satu laman) menghasilkan ukuran dokumen JSON-LD > 2 MB. Hal ini melanggar limit pembacaan buffer memori Googlebot (sekitar 15 MB total HTML DOM limit) dan memperlambat *First Meaningful Paint*.
- **Mitigasi**: Batasi *depth boundary* graf lokal hingga kedalaman maksimal 2 level (*immediate parent-child context*). Entitas turunan lebih jauh harus dirujuk menggunakan Absolute Canonical URLs tanpa mengekspansi seluruh cabangnya di dokumen yang sama.

---

## 8. Trade-offs & Alternatif Solusi

| Kriteria | Microdata / RDFa (Inline) | Isolated JSON-LD Blocks | Interconnected `@graph` JSON-LD |
| :--- | :--- | :--- | :--- |
| **Separation of Concerns** | Buruk (Bercampur dengan markah presentasi HTML) | Bagus (Terisolasi di `<script>`), tetapi relasi rusak | Sangat Bagus (Terisolasi murni dalam satu script engine) |
| **Penyusunan Relasi (Topology)** | Rumit; rawan terputus jika DOM dimanipulasi framework UI | Mustahil/Fragmented; entitas berdiri sendiri tanpa konteks | Sempurna; setiap node terhubung kuat lewat pointer `@id` |
| **Overhead Ukuran DOM** | Tinggi (Mengotori tag HTML dengan atribut atribut berulang) | Rendah hingga Menengah | Paling Optimal (Tidak ada duplikasi informasi entitas) |
| **Kompatibilitas AI Parser** | Sedang; rentan kesalahan hierarki saat DOM di-pruning | Buruk; AI kesulitan menyimpulkan relasi antar-blok | Maksimal; format yang direkomendasikan W3C & didukung mesin modern |
| **Maintenance Cost** | Sangat Tinggi saat refactor struktur template UI | Rendah, namun rentan error semantik tak terdeteksi | Terpusat; mudah di-maintain menggunakan class builder |

---

## 9. Best Practices & Standard Industri

1. **Gunakan Canonical Fragment Identifiers Deterministi**: Definisikan konvensi penamaan URI internal yang ketat. 
   - Organization: `{base_url}/#organization`
   - Author: `{base_url}/authors/{slug}/#person`
   - Primary WebPage: `{current_url}#webpage`
   - Primary Content Article: `{current_url}#article`
2. **Harmonisasi Data Visual dan Semantik**: Google mewajibkan informasi yang dideklarasikan pada struktur data semantik **harus terlihat langsung** oleh pengguna di layar. Mendeklarasikan data semantik yang sengaja disembunyikan (*cloaking via JSON-LD*) akan memicu tindakan manual (*Manual Action Penalty*) untuk kategori manipulasi markup terstruktur.
3. **Eksploitasi Strict Type Enums**: Hindari tipe data bebas pada properti kritikal. Gunakan standar ISO untuk mata uang (`currency: "USD"`), bahasa (`inLanguage: "en-US"`), dan format ISO 8601 untuk penanggalan (`datePublished: "2026-03-31T08:00:00+07:00"`).
4. **Verifikasi Otomatis pada CI/CD**: Pasang pipeline audit terintegrasi yang memvalidasi output HTML terhadap Schema.org Validator API dan Google Rich Results Test API sebelum kode dideploy ke lingkungan produksi.

---

## 10. Hands-on Lab Exercise

### Deskripsi Masalah
Anda diminta membangun arsitektur Graph Engine untuk entitas korporat e-commerce global. Sistem harus mengekstraksi data halaman produk dan menyusun skema `@graph` JSON-LD lengkap yang menghubungkan:
1. Identitas Brand Pembuat (termasuk referensi ke URI entitas Wikidata resmi).
2. Data Penawaran Harga (*AggregateOffer*).
3. Penilaian Pengguna (*AggregateRating*).
4. Halaman Web Induk (*WebPage*) tempat entitas tersebut bertengger.

### Langkah Pengerjaan

#### Langkah 1: Siapkan Environment
Instal paket validasi yang dibutuhkan:
```bash
pip install pydantic requests
```

#### Langkah 2: Buat File `ecommerce_graph_lab.py`
Tulis script implementasi berikut yang menyatukan seluruh relasi entitas:

```python
"""
Hands-on Lab: Enterprise E-commerce Entity Linking & Graph Construction
"""

import json
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional

class Brand(BaseModel):
    id: str = Field(..., alias="@id")
    type: str = Field(default="Brand", alias="@type")
    name: str
    sameAs: HttpUrl

class AggregateOffer(BaseModel):
    type: str = Field(default="AggregateOffer", alias="@type")
    lowPrice: float
    highPrice: float
    priceCurrency: str = Field(default="USD")
    offerCount: int

class AggregateRating(BaseModel):
    type: str = Field(default="AggregateRating", alias="@type")
    ratingValue: float
    reviewCount: int

class ProductNode(BaseModel):
    id: str = Field(..., alias="@id")
    type: str = Field(default="Product", alias="@type")
    name: str
    sku: str
    brand: dict
    offers: AggregateOffer
    aggregateRating: AggregateRating

class WebPageNode(BaseModel):
    id: str = Field(..., alias="@id")
    type: str = Field(default="WebPage", alias="@type")
    url: HttpUrl
    name: str
    mainEntity: dict

def generate_ecommerce_graph():
    base_url = "https://store.hardware-enterprise.com"
    sku = "SKU-HPC-9988"
    product_path = f"{base_url}/products/{sku.lower()}"
    
    # 1. Definisikan Entity Pointer IDs
    brand_id = f"{base_url}/brands/nvidia/#brand"
    product_id = f"{product_path}/#product"
    webpage_id = f"{product_path}/#webpage"

    # 2. Susun Node
    brand_node = Brand(
        id=brand_id,
        name="NVIDIA",
        sameAs="https://www.wikidata.org/wiki/Q182477" # type: ignore
    )

    product_node = ProductNode(
        id=product_id,
        name="Enterprise AI Accelerator 1000X",
        sku=sku,
        brand={"@id": brand_id},
        offers=AggregateOffer(
            lowPrice=9999.00,
            highPrice=10499.00,
            priceCurrency="USD",
            offerCount=5
        ),
        aggregateRating=AggregateRating(
            ratingValue=4.9,
            reviewCount=128
        )
    )

    webpage_node = WebPageNode(
        id=webpage_id,
        url=product_path, # type: ignore
        name="Beli Enterprise AI Accelerator 1000X - Akselerasi Model Skala Besar",
        mainEntity={"@id": product_id}
    )

    # 3. Rakit Topologi @graph
    full_graph = {
        "@context": "https://schema.org",
        "@graph": [
            webpage_node.model_dump(by_alias=True),
            product_node.model_dump(by_alias=True),
            brand_node.model_dump(by_alias=True)
        ]
    }
    
    return json.dumps(full_graph, indent=2)

if __name__ == "__main__":
    output = generate_ecommerce_graph()
    print(output)
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan modul tersebut di terminal:
```bash
python ecommerce_graph_lab.py
```

#### Langkah 4: Uji Validasi Mesin Pencari
1. Salin teks keluaran JSON-LD dari konsol terminal.
2. Buka peramban dan navigasikan ke [Validator Schema.org Resmi](https://validator.schema.org/).
3. Pilih opsi **Code Snippet**, tempel payload JSON-LD tersebut, lalu klik **Run Test**.
4. Amati struktur graf pada panel kanan: Pastikan tidak terdapat error, tidak ada entitas yang terduplikasi secara parsial, dan node `WebPage` secara valid mereferensikan node `Product`, yang selanjutnya secara valid mereferensikan node `Brand` ke entitas Wikidata yang bersangkutan.