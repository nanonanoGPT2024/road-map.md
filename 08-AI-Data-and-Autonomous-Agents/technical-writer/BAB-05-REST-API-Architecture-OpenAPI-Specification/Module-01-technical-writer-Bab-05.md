# Bab 05: REST API Architecture & OpenAPI Specification

## Module 01: Fondasi RESTful Architecture & OpenAPI 3.1 untuk Integrasi AI Agent

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Menerapkan** enam batasan arsitektur REST (*Roy Fielding Constraints*) dalam konteks integrasi sistem modern dan konsumsi data terstruktur oleh mesin.
- **Merancang dan Menulis** spesifikasi OpenAPI 3.1.x yang valid, *zero-drift*, dan dioptimalkan secara leksikal maupun semantik untuk dikonsumsi oleh *Large Language Models* (LLM) melalui mekanisme *Tool Calling* / *Function Calling*.
- **Mengimplementasikan** RFC 9457 (*Problem Details for HTTP APIs*) sebagai standar respons kesalahan deterministik yang dapat diparsing oleh *Autonomous Agents*.
- **Mengembangkan** *pipeline* validasi kontrak API otomatis menggunakan *linter* berbasis aturan (Spectral) dalam siklus hidup CI/CD dokumentasi teknis.
- **Mentransformasi** spesifikasi OpenAPI menjadi *schema-compatible payloads* untuk *agentic frameworks* (seperti LangChain, LlamaIndex, atau OpenAI Assisstant API) tanpa kehilangan konteks parameter.

---

### 2. Concept Overview

Secara historis, dokumentasi API diposisikan sebagai artefak pasif yang ditujukan khusus bagi pembaca manusia (*software engineers*). Namun, dalam lanskap **AI, Data, and Autonomous Agents**, API contract bertransformasi menjadi **antarmuka eksekusi mesin (*machine execution interface*)**. 

Arsitektur REST (*Representational State Transfer*) mendefinisikan prinsip-prinsip komunikasi *stateless*, berbasis *resource*, dan menggunakan metode HTTP baku (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`). 

OpenAPI Specification (OAS) 3.1.x merupakan evolusi krusial dalam rekayasa perangkat lunak modern. Berbeda dari OAS 3.0, OpenAPI 3.1 menyelaraskan sistem tipe datanya secara penuh (100% dialek identik) dengan **JSON Schema Draft 2020-12**. Keselarasan ini memungkinkan definisi skema yang sangat presisi melalui kata kunci seperti `type` berbasis *array* (contoh: `["string", "null"]`), `prefixItems` untuk *tuples*, serta dukungan penuh terhadap `unevaluatedProperties`.

```
        Mental Model: The Dual-Consumer Contract Paradigm
        
    +-----------------------------------------------------------+
    |                    OpenAPI 3.1 Spec                       |
    |            (Single Source of Truth / Contract)            |
    +-----------------------------+-----------------------------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
  [ Human Consumers ]                         [ Machine Consumers ]
  - Developer Portals (Redoc)                 - Autonomous Agents / LLMs
  - Interactive Consoles (Swagger)            - Tool/Function Calling Engines
  - Integration Engineers                     - Contract-Testing Runners
            |                                           |
            v                                           v
   Memahami Logika Bisnis                      Mengeksekusi RPC Dinamis
   dan Konteks Integrasi                       tanpa Halusinasi Parameter
```

Dalam paradigma *Agentic AI*, spesifikasi OpenAPI bertindak sebagai **definisi aksi sistem (*action space definition*)**. Ketika LLM diberikan akses ke *external tools*, LLM membedah OpenAPI Specification untuk mengekstrak:
1. **Intensi Operasi**: Diambil dari `summary` dan `description`.
2. **Kebutuhan Argumen**: Diambil dari `parameters`, `requestBody`, serta constraint validasi (`pattern`, `enum`, `minimum`, `maximum`).
3. **Penanganan Status Kegagalan**: Memahami skema respons HTTP `4xx` dan `5xx` untuk melakukan *self-correction* atau *retry loop*.

---

### 3. Why It Matters

Ketidakakuratan dokumentasi API dalam arsitektur konvensional menghasilkan *developer friction* dan *ticket escalations*. Namun, dalam arsitektur berbasis *Autonomous Agents*, ketidakakuratan atau ambiguitas dokumentasi API mengakibatkan **kegagalan eksekusi deterministik, *infinite loops*, kebocoran data, atau halusinasi inferensi**.

Kebutuhan level enterprise mencakup:
- **Mitigasi Halusinasi Parameter**: LLM tidak mengetahui *edge case* sebuah database backend. Jika *endpoint* memerlukan parameter format UUIDv4 tetapi OpenAPI hanya mendefinisikan tipe `string`, LLM dapat memasukkan nilai string arbitrer yang berujung pada HTTP `400 Bad Request`.
- **Optimalisasi Token Budget**: Spesifikasi OpenAPI yang bertele-tele atau tidak terstruktur menguras *context window* LLM secara sia-sia. Dokumentasi teknis harus ringkas secara token, namun kaya secara semantik operasional.
- **Contract-Driven Governance**: Standarisasi penamaan, skema error (RFC 9457), dan autentikasi multi-tenant memastikan ribuan *microservices* dapat diindeks oleh AI katalog enterprise secara instan tanpa modifikasi kode manual.

---

### 4. Architecture & Component Diagram

Berikut adalah alur arsitektural di mana spesifikasi OpenAPI 3.1 difungsikan ganda: sebagai dokumentasi interaktif untuk developer dan sebagai *action engine schema* bagi Autonomous AI Agent.

```
+---------------------------------------------------------------------------------------+
|                                CI/CD & SPEC REPOSITORY                                |
|                                                                                       |
|   +-----------------------+              +----------------------------------------+   |
|   |   OpenAPI 3.1 Spec    | --(lint)-->  | Spectral Engine (Ruleset Enforcement)  |   |
|   |  (YAML / Source File) |              +----------------------------------------+   |
|   +-----------+-----------+                                                           |
+---------------|-----------------------------------------------------------------------+
                |
                v (Build Artifact)
+------------------------------------+--------------------------------------------------+
| HUMAN CONSUMPTION PLANE            | MACHINE / AGENTIC PLANE                          |
|                                    |                                                  |
|   +----------------------------+   |   +------------------------------------------+   |
|   | Static Documentation Site  |   |   | OpenAPI Parser & Schema Flattener        |   |
|   | (Scalar / Redocly / Stoplight) |   +--------------------+---------------------+   |
|   +--------------+-------------+   |                        |                         |
|                  |                 |                        v                         |
|                  v                 |   +------------------------------------------+   |
|         [ Software Engineer ]      |   | LLM Tool Calling Converter               |   |
|                                    |   | (Pydantic / Function Calling JSON Schema)|   |
|                                    |   +--------------------+---------------------+   |
|                                    |                        |                         |
|                                    |                        v                         |
|                                    |   +------------------------------------------+   |
|                                    |   | Autonomous Agent Runtime                 |   |
|                                    |   | (Context Engine / ReAct Loop)            |   |
|                                    |   +--------------------+---------------------+   |
|                                    |                        |                         |
+------------------------------------+------------------------|-------------------------+
                                                              |
                                                              v (HTTP/1.1 or HTTP/2)
                                             +------------------------------------------+
                                             | API Gateway / Reverse Proxy (Kong/Envoy) |
                                             +--------------------+---------------------+
                                                                  |
                                                                  v
                                             +------------------------------------------+
                                             | REST Microservices (FastAPI / RFC 9457)  |
                                             +------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Roy Fielding REST Architectural Constraints
Untuk membangun REST API yang sejati, sistem wajib mematuhi 6 batasan dasar:
1. **Client-Server Architecture**: Pemisahan tegas antara UI/state consumer (Client) dari data storage dan domain logic (Server).
2. **Statelessness**: Setiap request dari client harus mengandung seluruh informasi yang diperlukan server untuk memahami dan mengeksekusi request tersebut. Session state disimpan sepenuhnya di sisi client (misalnya via JWT).
3. **Cacheability**: Respons harus secara eksplisit mendefinisikan dirinya dapat di-cache atau tidak (menggunakan HTTP header `Cache-Control`, `ETag`) untuk mencegah pengambilan data redundan.
4. **Layered System**: Client tidak dapat mengetahui secara persis apakah ia terhubung langsung ke end server atau melalui perantara (load balancer, API gateway, cache proxy).
5. **Code on Demand (Opsional)**: Kemampuan server mentransfer logic eksekusi ke client (misal: script JavaScript).
6. **Uniform Interface**: Inti diferensiasi REST, yang mencakup identifikasi resource via URI, manipulasi resource melalui representasi, self-descriptive messages, dan HATEOAS (*Hypermedia As The Engine Of Application State*).

#### 5.2 OpenAPI 3.1 & JSON Schema Draft 2020-12
Perbedaan fundamental antara OpenAPI 3.0 dan 3.1 terletak pada penyatuan tipe skema:
- **Nullability**: OpenAPI 3.0 menggunakan atribut terpisah `nullable: true`. OpenAPI 3.1 menggunakan array type standar JSON Schema: `type: ["string", "null"]`.
- **Polymorphism**: Pemanfaatan `anyOf`, `oneOf`, `allOf`, dan `not` dievaluasi sepenuhnya menggunakan aturan validasi JSON Schema Draft 2020-12.
- **Prefix Items**: Memungkinkan validasi array dengan struktur tipe terurut (tuple-like schema validation).

#### 5.3 Menulis Deskripsi Operasi yang Bersifat "LLM-Optimized"
Ketika LLM menggunakan Tool Calling, LLM membaca field `description` pada skema OpenAPI untuk menentukan *kapan* dan *bagaimana* sebuah fungsi harus dipanggil.
- **Anti-pattern**: `description: "Mengambil data pengguna."` (Terlalu ambigu, memicu kesalahan saat agent harus memilih antara endpoint pencarian atau endpoint detail).
- **Best Practice**: `description: "Mengambil profil pengguna spesifik berdasarkan UUIDv4 unik. Gunakan endpoint ini HANYA JIKA 'user_id' telah diketahui secara pasti. JANGAN gunakan untuk pencarian parsial berdasarkan nama."`

#### 5.4 Standarisasi Error: RFC 9457 (Problem Details)
Agen otonom memerlukan format error yang seragam untuk mengidentifikasi kegagalan dan menentukan langkah remediasi. RFC 9457 menetapkan struktur JSON media type `application/problem+json`:
- `type`: URI referensi yang mengidentifikasi tipe masalah.
- `title`: Ringkasan singkat masalah (stabil, tidak berubah per insiden).
- `status`: Kode status HTTP.
- `detail`: Penjelasan spesifik manusia/mesin terkait insiden yang terjadi.
- `instance`: URI referensi spesifik terjadinya insiden request.
- *Extensions*: Field kustom seperti `invalid_params` yang menunjukkan lokasi kegagalan validasi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi endpoint REST berbasis **FastAPI (Python 3.11+)** yang dirancang khusus untuk menghasilkan spesifikasi OpenAPI 3.1 secara native, mematuhi RFC 9457 untuk error handling, dan menyediakan metadata teroptimasi bagi AI Agent yang melakukan *tool calling* pada sistem Vector Data/Knowledge Base Retrieval.

```python
"""
Module: Knowledge Base Retrieval Service
Architecture: RESTful API compliant with OpenAPI 3.1 and RFC 9457.
Target Audience: Human Integrators & LLM Autonomous Agents.
"""

from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime
import uvicorn
from fastapi import FastAPI, Request, status, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


# ==============================================================================
# RFC 9457 ERROR MODELS
# ==============================================================================

class ProblemDetails(BaseModel):
    """Representasi standar kegagalan HTTP sesuai RFC 9457."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: HttpUrl = Field(
        default="https://api.enterprise.ai/errors/unhandled-exception",
        description="URI referensi mutlak yang mengidentifikasi kategori masalah.",
    )
    title: str = Field(
        ...,
        description="Ringkasan pendek dan dapat dibaca mengenai tipe masalah.",
        examples=["Invalid Query Parameters"]
    )
    status: int = Field(
        ...,
        description="Kode status HTTP yang dihasilkan oleh origin server.",
        ge=400,
        le=599,
        examples=[422]
    )
    detail: str = Field(
        ...,
        description="Penjelasan detail yang spesifik terhadap insiden ini.",
        examples=["Parameter 'limit' tidak boleh melampaui angka 50."]
    )
    instance: str = Field(
        ...,
        description="URI referensi spesifik yang mengidentifikasi terjadinya masalah.",
        examples=["/api/v1/knowledge-retrieval/sub-12345"]
    )
    invalid_params: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Daftar parameter yang gagal dalam tahap validasi skema."
    )


# ==============================================================================
# DOMAIN DTO MODELS (OPENAPI 3.1 & AGENT FRIENDLY)
# ==============================================================================

class DocumentChunk(BaseModel):
    chunk_id: UUID = Field(
        ...,
        description="Identifier unik UUIDv4 dari chunk teks yang ditemukan."
    )
    content: str = Field(
        ...,
        description="Konten teks semantik hasil segmentasi dokumen rujukan."
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Skor kedekatan kosinus vektor (0.0 = ortogonal, 1.0 = identik)."
    )
    source_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata sumber dokumen: { 'author': str, 'published_at': str, 'uri': str }."
    )


class KnowledgeSearchResponse(BaseModel):
    query: str = Field(..., description="Query asli yang dievaluasi.")
    total_chunks: int = Field(..., ge=0, description="Jumlah potongan teks yang berhasil ditemukan.")
    execution_time_ms: float = Field(..., ge=0.0, description="Durasi eksekusi pencarian vektor (milidetik).")
    results: List[DocumentChunk] = Field(
        ...,
        description="Daftar chunk dokumen terurut berdasarkan tingkat relevansi tertinggi."
    )


# ==============================================================================
# FASTAPI APPLICATION DEFINITION
# ==============================================================================

app = FastAPI(
    title="Enterprise AI Knowledge Retrieval Engine",
    version="1.2.0",
    summary="High-Performance Semantic Vector Retrieval API",
    description=(
        "API ini menyediakan antarmuka akses terprogram ke Vector Store perusahaan. "
        "Didesain khusus untuk dieksekusi langsung oleh Autonomous Agents (Tool/Function Calling) "
        "maupun developer frontend RAG pipeline. Menggunakan format RFC 9457 untuk pelaporan error."
    ),
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)


# ==============================================================================
# EXCEPTION HANDLERS (RFC 9457 CONFORMANCE)
# ==============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Mencegat error validasi Pydantic dan mentransformasikannya ke format RFC 9457."""
    errors = []
    for err in exc.errors():
        errors.append({
            "name": ".".join([str(loc) for loc in err["loc"] if loc != "query"]),
            "reason": err["msg"],
            "type": err["type"]
        })

    problem = ProblemDetails(
        type="https://api.enterprise.ai/errors/validation-error",  # type: ignore
        title="Schema Validation Error",
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Satu atau lebih parameter request tidak memenuhi batasan skema OpenAPI 3.1.",
        instance=str(request.url.path),
        invalid_params=errors
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        media_type="application/problem+json",
        content=problem.model_dump(exclude_none=True)
    )


# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================

@app.get(
    "/api/v1/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Query Vector Knowledge Base",
    operation_id="query_vector_knowledge_base",
    responses={
        200: {
            "description": "Pencarian semantik berhasil dilakukan.",
            "content": {"application/json": {"schema": KnowledgeSearchResponse.model_json_schema()}}
        },
        422: {
            "description": "Unprocessable Entity - Validasi parameter input gagal.",
            "content": {"application/problem+json": {"schema": ProblemDetails.model_json_schema()}}
        },
        500: {
            "description": "Internal Server Error - Kegagalan pada vector index cluster.",
            "content": {"application/problem+json": {"schema": ProblemDetails.model_json_schema()}}
        }
    }
)
async def search_knowledge_base(
    q: Annotated[
        str,
        Query(
            ...,
            min_length=3,
            max_length=512,
            description=(
                "Frasa pencarian semantik (natural language query). "
                "AI Agent: Masukkan teks pertanyaan pengguna secara langsung, bukan kata kunci boolean."
            ),
            examples=["Bagaimana kebijakan penanganan data pribadi GDPR pada sistem audit?"]
        )
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=25,
            description="Batas maksimum chunk dokumen yang dikembalikan (1-25). Rekomendasi agen: 3-5 untuk menghemat token.",
            examples=[5]
        )
    ] = 5,
    threshold: Annotated[
        float,
        Query(
            ge=0.5,
            le=1.0,
            description="Ambang batas (threshold) minimum cosine similarity. Angka lebih tinggi menghasilkan chunk yang lebih relevan.",
            examples=[0.75]
        )
    ] = 0.70
) -> KnowledgeSearchResponse:
    """
    Eksekusi pencarian vektor terhadap cluster pengetahuan perusahaan.
    
    Catatan Operasional bagi LLM / Agent:
    - Fungsi ini **idempoten** (`GET`). Aman dipanggil berulang kali tanpa efek samping manipulasi data.
    - Parameter `threshold` di bawah 0.70 akan meningkatkan *noise* (potongan teks tidak relevan).
    """
    start_time = datetime.utcnow()
    
    # Mocking Vector Search Retrieval Process
    mock_results = [
        DocumentChunk(
            chunk_id=UUID("c2960662-7f7a-4c2d-905e-856e72d24d27"),
            content="Seluruh pemrosesan identitas personal (PII) wajib dienkripsi at-rest menggunakan AES-256.",
            similarity_score=0.88,
            source_metadata={"document": "Security-Baseline-v2.pdf", "page": 12}
        )
    ]
    
    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000.0

    return KnowledgeSearchResponse(
        query=q,
        total_chunks=len(mock_results),
        execution_time_ms=execution_time,
        results=mock_results
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

---

### 7. Edge Cases & Failure Modes

| Skenario Kegagalan | Akar Masalah (Root Cause) | Dampak pada AI Agent / Integrator | Strategi Mitigasi & Error Recovery |
| :--- | :--- | :--- | :--- |
| **Schema Drift** | Developer mengubah signature payload response backend tanpa mengupdate skema OpenAPI. | Agent mengalami *deserialization crash* atau LLM gagal mengekstrak field jawaban yang hilang. | Pasang *Contract Testing* (Dredd atau Schemathesis) di pipeline pull request untuk memverifikasi kesesuaian runtime vs spec. |
| **Token Exhaustion (Context Blowout)** | Spesifikasi OpenAPI memiliki ribuan baris definisi objek rekursif yang dimasukkan mentah-mentah ke konteks LLM. | Window context model terisi penuh, biaya inferensi membengkak, penurunan *reasoning quality*. | Implementasikan modul *Schema Pruning* / *Flattener* yang hanya menyaring `operationId`, `parameters`, dan skema respons minimal yang relevan dengan tugas agen. |
| **Ambiguous Enums & Format** | Field bertipe string tidak diberikan `enum` atau `pattern` Regex, hanya deskripsi verbal. | LLM menghasilkan nilai arbitrer (misal: format tanggal `"12-05-2024"` alih-alih ISO-8601 `"2024-05-12T00:00:00Z"`). | Gunakan validasi skema OpenAPI 3.1 `format: date-time` dan deklarasikan `pattern` secara eksplisit. |
| **Non-Standard Error Schema** | Server mengembalikan HTML mentah (misal dari NGINX `502 Bad Gateway`) atau plain text. | Agent parser melempar unhandled parsing exception, memutus loop otonom. | Konfigurasikan fallback reverse-proxy untuk selalu membungkus response error ke media type `application/problem+json`. |

---

### 8. Trade-offs & Alternatif Solusi

Dalam arsitektur *Agent-to-API Communication*, REST + OpenAPI bukan satu-satunya pilihan. Berikut perbandingannya:

```
+-----------------------------------------------------------------------------------------+
|                  ARCHITECTURAL DECISION MATRIX: INTEGRATION PROTOCOLS                   |
+-------------------+----------------------+-----------------------+----------------------+
| Kriteria          | REST + OpenAPI 3.1   | GraphQL               | gRPC / Protocol Buff |
+-------------------+----------------------+-----------------------+----------------------+
| Standar Mesin     | Sangat Tinggi        | Sedang                | Tinggi (Protobuf IDL)|
| (LLM Tool Calling)| (Didukung Native     | (Perlu parsing AST    | (Perlu runtime proto |
|                   | semua LLM API)       | schema khusus)        | compilation di agent)|
+-------------------+----------------------+-----------------------+----------------------+
| Network Overhead  | Sedang (JSON Payload)| Rendah-Sedang         | Minimal (Binary,     |
|                   | & HTTP Headers)      | (Hanya field terpilih)| Multiplexing HTTP/2) |
+-------------------+----------------------+-----------------------+----------------------+
| Caching Support   | Native HTTP          | Kompleks              | Sulit                |
|                   | (Edge/Proxy Cache)   | (Mayoritas POST)      | (Custom Logic)       |
+-------------------+----------------------+-----------------------+----------------------+
| Schema Precision  | Sangat Tinggi        | Tinggi (Type Strict,  | Paling Ketat         |
|                   | (JSON Schema 2020-12)| tapi minus JSON Schema| (Strict Typed,       |
|                   |                      | validation constraints) proto3 definitions)   |
+-------------------+----------------------+-----------------------+----------------------+
| Rekomendasi Penggunaan:                                                                 |
| - REST + OpenAPI: Default mutlak untuk API publik, enterprise gateway, dan AI Tools.     |
| - GraphQL: Backend-For-Frontend (BFF) aplikasi web interaktif dengan relasi data tinggi. |
| - gRPC: Komunikasi antar-microservice internal ultra-low latency & high throughput.   |
+-----------------------------------------------------------------------------------------+
```

---

### 9. Best Practices & Standar Industri

#### 9.1 Spectral Ruleset Governance
Gunakan Spectral (linter OpenAPI dari Stoplight) dalam pipeline CI untuk menegakkan aturan desain teknis. Contoh `.spectral.yaml` tingkat enterprise:

```yaml
extends: [[spectral:oas, all]]
rules:
  # Memastikan setiap operasi memiliki deskripsi eksplisit untuk LLM
  operation-description:
    description: "Setiap operasi API wajib memiliki field 'description' yang komprehensif."
    message: "Operasi {{path}} ({{method}}) tidak memiliki field 'description'."
    severity: error
    given: $.paths.*[get,post,put,delete,patch]
    then:
      field: description
      function: truthy

  # Menegakkan penamaan kebab-case pada path URI
  paths-kebab-case:
    description: "URI path harus menggunakan standar kebab-case."
    message: "{{property}} bukan format kebab-case yang valid."
    severity: warn
    given: $.paths[*]~
    then:
      function: pattern
      functionOptions:
        match: "^(/|[a-z0-9-~._]|%[0-9a-fA-F]{2})+$"

  # Memastikan skema error menggunakan RFC 9457
  rfc-9457-error-response:
    description: "Respons error (4xx/5xx) wajib mendefinisikan media type application/problem+json."
    severity: error
    given: $.paths.*[get,post,put,delete,patch].responses[?(@property.match(/^(4\|5)/))]
    then:
      field: content
      function: defined
```

#### 9.2 Panduan Versi API (API Versioning)
Gunakan pendekatan **URI Path Versioning** (`/api/v1/...`) untuk perubahan besar yang melanggar kompatibilitas mundur (*breaking changes*). 
- *Breaking changes*: Menghapus endpoint, mengubah tipe data properti, menambah parameter *required* pada request body.
- *Non-breaking changes*: Menambah endpoint baru, menambah properti opsional (*optional field*) pada respons.

#### 9.3 Standar Autentikasi
Definisikan skema keamanan dalam blok `components.securitySchemes` menggunakan standar OAuth2 atau OpenID Connect Discovery:

```yaml
components:
  securitySchemes:
    OAuth2Bearer:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: "Masukkan JWT Bearer Token dengan format: Bearer <token>"
security:
  - OAuth2Bearer: []
```

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah *Lead Technical Writer & API Architect* pada startup AI Agents. Tim engineering telah menyelesaikan prototipe REST API untuk "Agent Web Scraping & Semantic Parser". Anda ditugaskan untuk:
1. Menulis spesifikasi kontrak OpenAPI 3.1 manual berbasis YAML.
2. Melakukan *linting* spesifikasi tersebut terhadap aturan ketat enterprise menggunakan CLI.
3. Menulis skrip adapter Python untuk mengonversi spesifikasi OpenAPI 3.1 tersebut menjadi format **OpenAI Function Calling Tool Schema**.

---

#### Langkah 1: Menulis Dokumen OpenAPI 3.1 YAML
Buat berkas bernama `agent-scraper-spec.yaml`:

```yaml
openapi: 3.1.0
info:
  title: Autonomous Web Scraping Service
  version: 1.0.0
  description: API untuk mengekstrak teks bersih dan metadata dari halaman web target secara asinkron.
servers:
  - url: https://scraper.enterprise.ai/v1
    description: Production Cluster
paths:
  /scrape:
    post:
      operationId: trigger_web_scrape
      summary: Scrape and parse web content
      description: Mengeksekusi rendering headless browser pada halaman URL target untuk mengekstrak teks markdown bersih. JANGAN gunakan pada file binary (PDF/Zip).
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - target_url
              properties:
                target_url:
                  type: string
                  format: uri
                  description: Alamat web lengkap yang valid diawali dengan http:// atau https://.
                  examples: ["https://docs.python.org/3/"]
                render_js:
                  type: boolean
                  default: false
                  description: Aktifkan eksekusi JavaScript (SPA) jika situs memerlukan rendering sisi klien.
      responses:
        "200":
          description: Ekstraksi halaman berhasil.
          content:
            application/json:
              schema:
                type: object
                required:
                  - status
                  - content_markdown
                properties:
                  status:
                    type: string
                    enum: ["success", "partial"]
                  content_markdown:
                    type: string
                    description: Teks hasil ekstraksi yang telah dikonversi ke format markdown.
        "422":
          description: Parameter request tidak valid.
          content:
            application/problem+json:
              schema:
                $ref: "#/components/schemas/ProblemDetails"
components:
  schemas:
    ProblemDetails:
      type: object
      required:
        - type
        - title
        - status
        - detail
      properties:
        type:
          type: string
          format: uri
        title:
          type: string
        status:
          type: integer
        detail:
          type: string
```

---

#### Langkah 2: Setup Spectral Linter & Validasi
Jalankan validasi spesifikasi OpenAPI menggunakan Node.js CLI:

```bash
# Instalasi spectral CLI secara global atau via npx
npx @stoplight/spectral-cli lint agent-scraper-spec.yaml --display-only-failures
```

*Verifikasi:* Pastikan terminal menampilkan `OpenAPI 3.1.x file passed linting with 0 errors` sebelum melangkah ke proses konversi tool.

---

#### Langkah 3: Konversi OpenAPI 3.1 ke Format LLM Tool Definition
Jalankan script Python berikut untuk memverifikasi bahwa spesifikasi OpenAPI 3.1 yang telah Anda tulis dapat langsung di-*ingest* oleh LLM Runtime (OpenAI Tool Calling spec):

```python
"""
Script: openapi_to_tool.py
Fungsi: Mengurai OpenAPI 3.1 spec lokal dan mengekstrak definisi operasi 
        menjadi OpenAI Function Calling parameter object.
"""

import json
import yaml

def convert_openapi_operation_to_tool(spec_path: str, operation_id: str) -> dict:
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # Menelusuri endpoint yang sesuai dengan operationId
    target_op = None
    target_method = None
    target_path = None

    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if op.get("operationId") == operation_id:
                target_op = op
                target_method = method
                target_path = path
                break
        if target_op:
            break

    if not target_op:
        raise ValueError(f"Operation ID '{operation_id}' tidak ditemukan dalam spesifikasi.")

    # Ekstraksi payload schema dari requestBody JSON
    request_body_schema = (
        target_op.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )

    # Konstruksi struktur Tool OpenAI
    tool_definition = {
        "type": "function",
        "function": {
            "name": target_op["operationId"],
            "description": target_op.get("description", target_op.get("summary", "")),
            "parameters": {
                "type": "object",
                "properties": request_body_schema.get("properties", {}),
                "required": request_body_schema.get("required", [])
            }
        }
    }

    return tool_definition

if __name__ == "__main__":
    tool = convert_openapi_operation_to_tool("agent-scraper-spec.yaml", "trigger_web_scrape")
    print("HASIL TRANSKIP TOOL OPENAI COMPATIBLE:")
    print(json.dumps(tool, indent=2))
```

---

#### Verifikasi Hasil Output Lab
Jalankan file python tersebut:
```bash
python openapi_to_tool.py
```
Output terminal yang diekspektasikan:
```json
HASIL TRANSKIP TOOL OPENAI COMPATIBLE:
{
  "type": "function",
  "function": {
    "name": "trigger_web_scrape",
    "description": "Mengeksekusi rendering headless browser pada halaman URL target untuk mengekstrak teks markdown bersih. JANGAN gunakan pada file binary (PDF/Zip).",
    "parameters": {
      "type": "object",
      "properties": {
        "target_url": {
          "type": "string",
          "format": "uri",
          "description": "Alamat web lengkap yang valid diawali dengan http:// atau https://.",
          "examples": [
            "https://docs.python.org/3/"
          ]
        },
        "render_js": {
          "type": "boolean",
          "default": false,
          "description": "Aktifkan eksekusi JavaScript (SPA) jika situs memerlukan rendering sisi klien."
        }
      },
      "required": [
        "target_url"
      ]
    }
  }
}
```
Struktur JSON di atas adalah payload standar industri yang siap disuntikkan ke dalam API Call model LLM tingkat lanjut (`tools=[...]`), membuktikan bahwa penulisan OpenAPI 3.1 yang presisi menjembatani komunikasi data enterprise langsung ke ruang aksi Autonomous Agents.