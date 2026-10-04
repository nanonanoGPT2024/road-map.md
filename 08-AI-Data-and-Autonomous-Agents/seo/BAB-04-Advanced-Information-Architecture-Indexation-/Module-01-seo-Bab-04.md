# Bab 04: Advanced Information Architecture & Indexation Control
## Module 01: Engine Kontrol Indeksasi Terdistribusi & Arsitektur Graf Informasi Modern

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Memetakan Topologi Graf Arsitektur Informasi (IA):** Menghitung kedalaman *crawl depth* dan distribusi *internal PageRank* menggunakan representasi *Directed Acyclic Graph* (DAG) untuk mencegah perangkap indeksasi (*crawler traps*).
- **Merancang Mesin Kontrol Indeksasi Edge-Native:** Mengimplementasikan orkestrasi kontrol indeksasi dinamis via HTTP Header (`X-Robots-Tag`, `Link: rel="canonical"`, `Surrogate-Control`) pada *edge computing layer* (Cloudflare Workers/Fastly VCL/Edge Middleware).
- **Mengontrol Crawl Budget untuk Skala Enterprise:** Mengeliminasi pemborosan *crawl budget* pada faceted navigation dengan mengontrol *state-space explosion* URL menggunakan kombinasi canonical hashing, parameter stripping, dan dynamic response status.
- **Mengembangkan Dual-Plane Discovery Engine:** Memisahkan *discovery path* antara *traditional search engine bots* (Googlebot, Bingbot) dan *autonomous AI retrieval agents* (GPTBot, ClaudeBot, PerplexityBot) menggunakan arsitektur `llms.txt`, semantic sitemaps, dan selective rendering.
- **Mengidentifikasi & Memitigasi Edge Case Indeksasi Kritis:** Mendiagnosis dan memperbaiki *canonical loops*, *soft-404 leakage*, *CDN caching contamination* pada respons `noindex`, dan *orphan cluster fragmentation*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Arsitektur Informasi (IA) dalam domain *enterprise SEO* dan *AI agent discovery* bukan sekadar penataan menu navigasi, melainkan **rekayasa topologi graf berbasis probabilitas transit crawling**. Web crawler memandang platform web sebagai graf berarah $G = (V, E)$, di mana vertex ($V$) merepresentasikan dokumen/URL dan edge ($E$) merepresentasikan hyperlink (`<a href>`).

```
         Traditional Search (Googlebot)           Autonomous AI Agents (Perplexity/LLM)
                   │                                         │
                   ▼                                         ▼
         ┌───────────────────┐                     ┌───────────────────┐
         │ Rendering Engine  │                     │ Semantic Parser   │
         │ (Headless Chrome) │                     │ (RAG / Context)   │
         └─────────┬─────────┘                     └─────────┬─────────┘
                   │                                         │
                   └─────────────────┐     ┌─────────────────┘
                                     ▼     ▼
                            ┌─────────────────────┐
                            │ Edge Ingestion Node │
                            │ (Policy Evaluation) │
                            └──────────┬──────────┘
                                       ▼
                   ┌───────────────────────────────────────┐
                   │  Indexation Control Engine (ICE)      │
                   │  - Canonical Graph DAG Evaluator      │
                   │  - Dynamic X-Robots Injector          │
                   │  - Token Bucket Crawl Rate Limiter    │
                   └───────────────────────────────────────┘
```

#### Dual-Paradigm: Web Search vs. AI Agent Discovery
1. **Search Crawlers (Information Retrieval 1.0/2.0):** Berfokus pada penyerapan HTML, eksekusi JavaScript (WRS - Web Rendering Service), pemrosesan *PageRank*, dan ekstraksi teks untuk pembentukan *inverted index*. Bottleneck utama: *compute rendering cost* dan *crawl budget*.
2. **AI Autonomous Agents (Information Retrieval 3.0):** Berfokus pada penyerapan *context-dense data*, ekstraksi entity relationship, ketersediaan API/markdown terstruktur, dan validasi *recency*. Bot AI sering kali membatasi eksekusi rendering JS yang berat demi memprioritaskan endpoint berlatensi rendah (`text/plain`, `text/markdown`, atau endpoint JSON terstruktur).

#### Mental Model: The Indexation State Machine
Setiap URL dalam sistem harus berada dalam state deterministik yang dikontrol oleh mesin kebijakan indeksasi terpusat:

$$\text{State}(U) \in \{\text{DISCOVERED}, \text{CRAWLED}, \text{INDEXABLE}, \text{CANONICALIZED}, \text{RESTRICTED}, \text{DROPPED}\}$$

Transisi state ini ditentukan oleh respons HTTP status, header `X-Robots-Tag`, relasi `canonical`, dan kualitas arsitektur semantik dokumen. Kegagalan mengontrol transisi ini secara deterministik berujung pada duplikasi konten, kanibalisasi kata kunci, serta penurunan visibilitas platform.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada skala enterprise (e-commerce dengan $10^7$ produk, portal media global, atau SaaS multi-tenant), kegagalan kontrol indeksasi memicu masalah katastropik:

1. **State-Space Explosion pada Faceted Navigation:** Kombinasi filter (warna, ukuran, rentang harga, urutan sortasi) memicu ekspansi URL secara faktorial:
   $$N = \sum_{k=1}^{M} \binom{M}{k} \times V_k$$
   Jika terdapat 10 jenis filter dengan rata-rata 5 nilai, crawler trap ini menciptakan miliaran URL tidak bernilai (*thin content*). Akibatnya, Googlebot menghabiskan 90% waktu crawling pada halaman filter duplikat, sementara halaman produk inti tidak pernah terindeks.
2. **CDN Cache Poisoning & Cross-Contamination:** Kesalahan konfigurasi CDN header `Cache-Control` pada halaman yang disuntikkan `noindex` secara dinamis dapat menyebabkan halaman berstatus `index` normal tersimpan di edge cache dengan direktif `noindex`, mendepak halaman transaksi utama dari Google SERP secara massal.
3. **Peningkatan Biaya Infrastruktur:** Crawler liar dan AI scraper yang mengeksekusi SSR (*Server-Side Rendering*) pada rute dinamis yang tidak terlindungi menguras kapasitas komputasi cluster backend (CPU/Memory spike), memicu degradasi layanan bagi pengguna nyata (*human visitors*).

---

### 4. Arsitektur & Diagram Komponen

Sistem kontrol indeksasi enterprise modern ditempatkan pada **Edge Layer** sebelum request diteruskan ke origin server atau SSR Node renderer.

```
[ Inbound HTTP Request ]
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. EDGE ROUTING & BOT IDENTIFIER (Cloudflare/Fastly/Envoy)   │
│    - Regex User-Agent Parser & ASN/rDNS Verification         │
│    - Category: SearchBot | AIAgent | MaliciousBot | Human   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. URL NORMALIZATION & GRAPH DEPTH ENGINE                   │
│    - Query Param Sanitization & Lexicographical Sorting      │
│    - Path Traversal Depth Calculator                         │
│    - Canonical Hash Evaluation (MD5/Murmur3 of Core State)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. INDEXATION POLICY ENGINE (State Evaluator)               │
│    - Canonical DAG Resolution                               │
│    - Taxonomy Breadcrumb Hierarchy Extraction                │
│    - Crawl Budget Token Bucket Enforcement                   │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
     [Dynamic Rule Applied]         [Fetch Dynamic Origin]
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│ 4. HEADER INJECTION PROXY    │ │ 5. SSR / STATIC ORIGIN     │
│  - X-Robots-Tag (Targeted)   │ │  - Raw HTML Body Payload   │
│  - Link: rel="canonical"     │ │  - Hydration JSON Data     │
│  - Surrogate-Key / Cache Tag │ │  - Microdata Semantic Graph│
└──────────────┬───────────────┘ └────────────┬───────────────┘
               │                              │
               └──────────────┬───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. RESPONSE EDGE HYDRATION                                  │
│    - Injeksi Alternatif llms.txt jika Bot == AIAgent         │
│    - Strip script tak berelasi untuk Bot rendering          │
│    - Set CDN Edge TTL vs Browser TTL via Surrogate-Control  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
[ Final HTTP Response to Client/Crawler ]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme Injeksi Kontrol Indeksasi Tingkat Protokol
Kontrol indeksasi via meta tag HTML (`<meta name="robots" content="...">`) memiliki kelemahan mendasar: browser dan crawler harus mengunduh dan mem-parsing seluruh atau sebagian stream HTML. Pada file non-HTML (PDF, JSON, Image) atau respons dinamis, meta tag tidak dapat dieksekusi.

Standar enterprise menggunakan **HTTP Response Header `X-Robots-Tag`**:
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=UTF-8
X-Robots-Tag: googlebot: noindex, follow, noarchive
X-Robots-Tag: gptbot: noindex, nofollow
Link: <https://example.com/canonical-slug>; rel="canonical"
Surrogate-Control: max-age=86400, stale-while-revalidate=3600
Cache-Control: public, max-age=0, must-revalidate
```
Dengan memanfaatkan nama spesifik bot pada `X-Robots-Tag`, kita dapat melakukan kontrol granular: mengizinkan Googlebot melakukan *indexing*, namun menolak AI agent melakukan ekstraksi untuk korpus pelatihan.

#### B. Canonical Graph DAG Resolver
URL canonical tidak boleh membentuk graf berulang (*circular references*) atau relasi multi-hop:
- **Buruk:** $A \to B \to C \to A$ (Circular Loop - Mesin indeksasi akan mengabaikan seluruh relasi dan memilih sembarang URL secara probabilistik).
- **Buruk:** $A \to B \to C$ (Multi-hop canonical - Melemahkan transmisi sinyal ranking/PageRank).
- **Enterprise Standard:** Resolusi $O(1)$ langsung ke *Terminal Node Canonical* yang valid: $\forall x \in \{A, B, C\}, \text{Canonical}(x) = T$.

#### C. Penanganan Faceted Navigation: Matrix Parameter Flattening
Ketika sistem menerima URL berfilter seperti:
`/catalog/shoes?sort=price_asc&color=red&page=2&size=42`

Mesin Kontrol Indeksasi mengevaluasi dimensi matriks:
1. **Sort Parameter (`sort`):** Bersifat presentasional, tidak menambah nilai semantik. Wajib di-strip dari canonical dan dipasangi `X-Robots-Tag: noindex, follow`.
2. **Multi-value Filters (`color`, `size`):** Jika kombinasi menghasilkan volume pencarian rendah ($< 10$ query/bulan via database metrik), sistem secara otomatis menerapkan *canonical consolidation* ke root category:
   `Link: <https://example.com/catalog/shoes>; rel="canonical"`
3. **Pagination (`page=2`):** Canonical harus bersifat **self-referential** (`/catalog/shoes?page=2`), dilarang diarahkan ke halaman 1, dan tidak dipasangi `noindex` agar crawling tautan internal ke produk di halaman-halaman dalam tidak terputus.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Edge-Grade Indexation Control Engine (ICE)** menggunakan Python dengan pendekatan asynchronous, arsitektur bersih (*Clean Architecture*), validasi Pydantic v2, dan pemrosesan DAG untuk canonical routing.

```python
"""
Indexation Control Engine (ICE) - Enterprise Edge Architecture
Komponen middleware untuk orkestrasi kontrol indeksasi, canonical resolution,
dan dynamic crawler policy enforcement.
"""

from __future__ import annotations

import enum
import re
from typing import Dict, List, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from pydantic import BaseModel, Field, HttpUrl


class CrawlerCategory(str, enum.Enum):
    SEARCH_ENGINE = "search_engine"
    AI_AGENT = "ai_agent"
    GENERIC_BOT = "generic_bot"
    HUMAN = "human"


class Directives(BaseModel):
    index: bool = True
    follow: bool = True
    noarchive: bool = False
    directives_extra: List[str] = Field(default_factory=list)

    def to_header_value(self) -> str:
        parts: List[str] = []
        parts.append("index" if self.index else "noindex")
        parts.append("follow" if self.follow else "nofollow")
        if self.noarchive:
            parts.append("noarchive")
        parts.extend(self.directives_extra)
        return ", ".join(parts)


class RequestContext(BaseModel):
    url: str
    user_agent: str
    is_https: bool = True
    base_domain: str = "example.com"


class IndexationResolution(BaseModel):
    status_code: int
    headers: Dict[str, str]
    canonical_url: str
    is_dropped: bool = False
    routing_action: str = "PASS"


class CanonicalDAGResolver:
    """Menyelesaikan Canonical Dependency Graph untuk mencegah circular dan multi-hop canonicals."""

    def __init__(self, routes: Optional[Dict[str, str]] = None) -> None:
        self._graph: Dict[str, str] = routes or {}

    def add_edge(self, source_path: str, canonical_path: str) -> None:
        self._graph[source_path] = canonical_path

    def resolve(self, path: str) -> str:
        visited: Set[str] = set()
        current: str = path

        while current in self._graph:
            if current in visited:
                # Circular canonical terdeteksi. Break ke self-canonical aman.
                return path
            visited.add(current)
            current = self._graph[current]

        return current


class IndexationEngine:
    """Mesin Analisis dan Eksekusi Kebijakan Indeksasi."""

    # Parameter yang tidak mengubah konten struktural halaman
    STRIPPED_PARAMS: Set[str] = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term",
        "utm_content", "gclid", "fbclid", "sort", "order"
    }

    AI_BOT_PATTERNS: List[re.Pattern] = [
        re.compile(r"GPTBot", re.IGNORECASE),
        re.compile(r"ClaudeBot", re.IGNORECASE),
        re.compile(r"PerplexityBot", re.IGNORECASE),
        re.compile(r"Bytespider", re.IGNORECASE),
    ]

    SEARCH_BOT_PATTERNS: List[re.Pattern] = [
        re.compile(r"Googlebot", re.IGNORECASE),
        re.compile(r"bingbot", re.IGNORECASE),
        re.compile(r"YandexBot", re.IGNORECASE),
    ]

    def __init__(self, dag_resolver: CanonicalDAGResolver) -> None:
        self.dag = dag_resolver

    def classify_bot(self, user_agent: str) -> CrawlerCategory:
        for pattern in self.AI_BOT_PATTERNS:
            if pattern.search(user_agent):
                return CrawlerCategory.AI_AGENT
        for pattern in self.SEARCH_BOT_PATTERNS:
            if pattern.search(user_agent):
                return CrawlerCategory.SEARCH_ENGINE
        if "bot" in user_agent.lower() or "crawl" in user_agent.lower():
            return CrawlerCategory.GENERIC_BOT
        return CrawlerCategory.HUMAN

    def normalize_url(self, raw_url: str) -> tuple[str, dict[str, list[str]]]:
        parsed = urlparse(raw_url)
        query_dict = parse_qs(parsed.query, keep_blank_values=False)

        # Hapus tracking & sorting parameter
        sanitized_query = {
            k: v for k, v in query_dict.items() if k.lower() not in self.STRIPPED_PARAMS
        }

        # Urutkan kunci query string untuk menghindari duplikasi kombinasi acak
        sorted_query = sorted(sanitized_query.items())
        reconstructed_query = urlencode(sorted_query, doseq=True)

        normalized_url = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip("/") if parsed.path != "/" else "/",
            "",
            reconstructed_query,
            ""  # Selalu hilangkan hash fragments pada edge layer
        ))

        return normalized_url, sanitized_query

    def calculate_crawl_depth(self, path: str) -> int:
        clean_path = path.strip("/")
        if not clean_path:
            return 0
        return len(clean_path.split("/"))

    def evaluate(self, ctx: RequestContext) -> IndexationResolution:
        try:
            bot_type = self.classify_bot(ctx.user_agent)
            normalized_url, query_params = self.normalize_url(ctx.url)
            parsed_normalized = urlparse(normalized_url)
            
            resolved_path = self.dag.resolve(parsed_normalized.path)
            depth = self.calculate_crawl_depth(resolved_path)

            # Inisialisasi direktif default
            directives = Directives(index=True, follow=True)
            headers: Dict[str, str] = {}
            status_code = 200
            action = "PASS"

            # 1. Penanganan Crawler Trap: Kedalaman Arsitektur Terlalu Dalam (> 5 level)
            if depth > 5:
                directives.index = False
                directives.follow = False
                action = "PREVENT_TRAP"

            # 2. Penanganan Faceted Navigation Explosion
            # Jika filter query param lebih dari 2 dimensi, blokir dari indeks
            if len(query_params) > 2:
                directives.index = False
                directives.follow = True
                action = "RESTRICT_FACETS"

            # 3. Kontrol Akses Berbeda Antara Search Engine vs AI Agents
            if bot_type == CrawlerCategory.AI_AGENT:
                # Batasi AI scraper jika parameter dynamic facet aktif
                if len(query_params) > 0:
                    headers["X-Robots-Tag"] = "noindex, nofollow"
                    return IndexationResolution(
                        status_code=403,
                        headers={"X-Robots-Tag": "noindex, nofollow"},
                        canonical_url=normalized_url,
                        is_dropped=True,
                        routing_action="BLOCK_AI_DEEP_CRAWL"
                    )
                # Berikan header kontekstual ketersediaan format LLM jika path utama
                headers["Link"] = f'</llms.txt>; rel="help"; type="text/plain"'

            # 4. Konstruksi Absolute Canonical URL dari Path Hasil Resolusi DAG
            canonical_canonical = urlunparse((
                "https" if ctx.is_https else "http",
                ctx.base_domain,
                resolved_path,
                "",
                urlencode(sorted(query_params.items()), doseq=True) if len(query_params) <= 2 else "",
                ""
            ))

            # Header standardisasi SEO & Crawl Control
            headers["X-Robots-Tag"] = directives.to_header_value()
            existing_link = headers.get("Link", "")
            canonical_link = f'<{canonical_canonical}>; rel="canonical"'
            headers["Link"] = f"{existing_link}, {canonical_link}".strip(", ")
            
            # Caching policy berbasis status bot
            if bot_type in (CrawlerCategory.SEARCH_ENGINE, CrawlerCategory.AI_AGENT):
                headers["Surrogate-Control"] = "max-age=86400, stale-while-revalidate=600"
            
            return IndexationResolution(
                status_code=status_code,
                headers=headers,
                canonical_url=canonical_canonical,
                is_dropped=False,
                routing_action=action
            )

        except Exception as err:
            # Fallback fail-safe: Jaga origin tetap jalan, terapkan noindex untuk proteksi
            fallback_canonical = f"https://{ctx.base_domain}/"
            return IndexationResolution(
                status_code=500,
                headers={
                    "X-Robots-Tag": "noindex, nofollow",
                    "Link": f'<{fallback_canonical}>; rel="canonical"',
                    "X-ICE-Error": "ExecutionFallbackTriggered"
                },
                canonical_url=fallback_canonical,
                is_dropped=False,
                routing_action="CRITICAL_FALLBACK"
            )


# ==========================================
# Unit Execution Verification & Test Pipeline
# ==========================================

if __name__ == "__main__":
    dag = CanonicalDAGResolver()
    # Daftarkan skenario multi-hop canonical: /shoes/sneakers/running -> /shoes/running -> /catalog/running-shoes
    dag.add_edge("/shoes/sneakers/running", "/shoes/running")
    dag.add_edge("/shoes/running", "/catalog/running-shoes")

    # Inisialisasi engine
    engine = IndexationEngine(dag_resolver=dag)

    # Uji Kasus 1: Faceted Navigation Kompleks dari Googlebot (Harus Noindex, Follow Canonical Target DAG)
    req1 = RequestContext(
        url="https://example.com/shoes/sneakers/running?sort=price_asc&utm_source=fb&color=red&size=42&gender=men",
        user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        is_https=True,
        base_domain="example.com"
    )
    res1 = engine.evaluate(req1)
    print("Test 1 Result (Googlebot Facet Trap):")
    print(f"Status Code     : {res1.status_code}")
    print(f"X-Robots-Tag    : {res1.headers.get('X-Robots-Tag')}")
    print(f"Link Header     : {res1.headers.get('Link')}")
    print(f"Resolved Canon  : {res1.canonical_url}")
    print(f"Action Taken    : {res1.routing_action}")
    assert res1.headers.get("X-Robots-Tag") == "noindex, follow"
    assert res1.canonical_url == "https://example.com/catalog/running-shoes"

    # Uji Kasus 2: Scraper AI mencoba crawling URL bervalue parameter (Harus 403 Dropped)
    req2 = RequestContext(
        url="https://example.com/catalog/running-shoes?color=blue",
        user_agent="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.0; +https://openai.com/gptbot)",
        is_https=True,
        base_domain="example.com"
    )
    res2 = engine.evaluate(req2)
    print("\nTest 2 Result (AI Scraper Facet Request):")
    print(f"Status Code     : {res2.status_code}")
    print(f"Action Taken    : {res2.routing_action}")
    assert res2.status_code == 403
    assert res2.is_dropped is True

    # Uji Kasus 3: Clean Canonical URL AI Discovery
    req3 = RequestContext(
        url="https://example.com/catalog/running-shoes",
        user_agent="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0)",
        is_https=True,
        base_domain="example.com"
    )
    res3 = engine.evaluate(req3)
    print("\nTest 3 Result (AI Scraper Clean Architecture):")
    print(f"Status Code     : {res3.status_code}")
    print(f"Link Header     : {res3.headers.get('Link')}")
    assert 'rel="help"; type="text/plain"' in res3.headers.get("Link", "")
    print("\nVerification Completed Successfully: All constraints validated.")
```

---

### 7. Edge Cases & Failure Modes

#### 1. The CDN Noindex Cache Contamination
- **Skenario:** Pengguna biasa memicu error 404/500 atau halaman dinamis yang disuntikkan header `X-Robots-Tag: noindex`. CDN (misal: Cloudflare/Akamai) meng-cache respons tersebut secara *public* berdasarkan nilai URL tanpa menyertakan variasi header `User-Agent`. Saat Googlebot meminta URL yang sama, CDN menyajikan file dari cache yang memiliki `noindex`.
- **Mitigasi Teknis:** 
  Wajib mengonfigurasi header `Vary: X-Robots-Tag` jika respons dinamis, atau memisahkan cache key CDN berdasarkan kategori crawler menggunakan Workers:
  ```http
  Vary: Accept-Encoding, User-Agent
  Cache-Control: private, no-cache, no-store, must-revalidate
  ```
  Untuk halaman statis yang di-cache, jangan sekali-kali mengubah nilai `X-Robots-Tag` berdasarkan User-Agent di layer downstream jika reverse-proxy Anda tidak memiliki fitur *custom cache key isolation*.

#### 2. Infinite Deep Pathing Loops (Relative Path Resolution Bug)
- **Skenario:** Tautan relatif di sisi client tanpa leading slash (`href="category/shoes"`) dipanggil berulang kali di halaman `/category/shoes`, menyebabkan crawler mengeksplorasi path:
  `/category/shoes/category/shoes/category/shoes/...`
- **Mitigasi Teknis:** Regex enforcement pada edge layer yang mendeteksi repetisi segment sub-path ($\ge 3$ pengulangan token yang identik) dan langsung melempar status `HTTP 410 Gone` atau me-rewrite request ke base canonical terminal secara permanen (`HTTP 301`).

#### 3. Canonical Loop Lock
- **Skenario:** Halaman A memiliki tag canonical ke B, dan halaman B memiliki canonical ke A. Search engine akan menganggap kedua canonical invalid, mendevaluasi kedua halaman, dan memilih salah satu versi secara acak yang berisiko menampilkan halaman usang di SERP.
- **Mitigasi Teknis:** Wajib memvalidasi DAG secara siklikal pada sistem build/CI-CD sitemap menggunakan algoritma *Tarjan's strongly connected components* atau *Depth-First Search* (DFS) path validation seperti yang diimplementasikan pada class `CanonicalDAGResolver` di atas.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Pendekatan | `robots.txt` Disallow | `X-Robots-Tag: noindex` | Edge Canonical Consolidation | Dynamic Parameter Stripping |
| :--- | :--- | :--- | :--- | :--- |
| **Crawl Budget Preservation** | **Sangat Tinggi** (Bot sama sekali tidak fetch URL) | **Rendah** (Bot wajib fetch dokumen untuk membaca header) | **Moderat** (Bot masih mengunduh dokumen secara parsial) | **Tinggi** (Mengurangi variasi link sebelum dirayapi) |
| **Pembersihan Index Terdaftar** | **Gagal** (Jika URL sudah ada di index, disallow mencegah bot membaca status drop) | **Sangat Cepat** (URL langsung didepak dari SERP) | **Lambat** (Tergantung transfer PageRank konsolidasi) | **Tidak Relevan** (Hanya mencegah duplikasi) |
| **Komputasi Backend** | Nol (Ditolak di level robots parser bot) | Butuh respon HTTP (Minimal hit ke Edge/CDN) | Butuh resolusi DAG di Edge layer | Rendah (Regex normalization di Edge) |
| **Dukungan Autonomous AI** | Parsial (Banyak bot AI kecil mengabaikan robots.txt) | **Tinggi** (Terbaca di response header parsing) | Diabaikan oleh RAG murni non-graph scraper | Bersih (Menjaga context vector database tetap homogen) |

---

### 9. Best Practices & Standar Industri

1. **Hierarchy Isolation Principle:** Kedalaman arsitektur direktori URL tidak boleh melebihi 3 hop dari domain root untuk konten esensial:
   `https://example.com/{taxonomy}/{sub-taxonomy}/{entity-id}`
2. **Deterministic Trailing Slash Enforcement:** Standarisasi semua URL menggunakan trailing slash atau tanpa trailing slash di level edge middleware via redirect 301 untuk menghindari splitting link equity ($G = (V_1, V_2)$ di mana keduanya identik secara representasi visual).
3. **HTTP Header Over HTML Tag:** Selalu prioritaskan `X-Robots-Tag` dan `Link: rel="canonical"` pada response header level. Hal ini menjamin integritas metadata sebelum crawler rendering queue mengeksekusi virtual browser (WRS).
4. **Autonomous AI Discovery Routing:** 
   Sediakan manifest discovery terpusat pada root:
   - Pasang file `/llms.txt` (format ringkas terstruktur untuk Context-Augmented Crawlers).
   - Layani respons `Accept: text/markdown` jika request berasal dari bot AI berizin, menghemat hingga 80% ukuran token context window scraper.
5. **Soft 404 Absolute Eradication:** Halaman pencarian internal tanpa hasil (*empty search results*) atau entitas kedaluwarsa dilarang keras menghasilkan status `HTTP 200 OK` dengan pesan "Barang Tidak Ditemukan". Kondisi ini wajib merespons dengan `HTTP 404 Not Found`, `HTTP 410 Gone`, atau minimal diinjeksi header `X-Robots-Tag: noindex, follow`.

---

### 10. Hands-on Lab Exercise: Membangun Edge Indexation Controller

#### Deskripsi Lab
Anda diminta untuk membangun dan menguji Edge Controller mini yang menghentikan *crawl budget bleeding* akibat faceted navigation trap pada aplikasi katalog high-traffic, sekaligus membuka akses semantik bagi autonomous AI scraper secara terkontrol.

#### Setup Lab
Buat file bernama `edge_controller_lab.py` dan jalankan menggunakan Python 3.10+:

```bash
# 1. Setup Virtual Environment & Dependencies
python3 -m venv venv
source venv/bin/activate
pip install pydantic fastapi httpx uvicorn
```

#### Langkah-langkah Implementasi:

1. **Definisikan Ruleset Matrix:**
   - Parameter `page` dipertahankan dan di-maintain secara canonical self-referential.
   - Parameter filter (`size`, `color`, `material`) jika berjumlah $\le 2$ diperbolehkan terindeks; jika $> 2$ dipasang `noindex, follow`.
   - Parameter sortasi (`order`, `sort_by`, `view`) harus selalu dibuang dari canonical URL dan dipasang `noindex`.
   - Bot kategori AI (`GPTBot`, `ClaudeBot`) yang mengakses halaman kategori dengan parameter apapun harus mendapatkan respon `403 Forbidden`, namun pada URL root/clean category diberikan header alternatif ke file Markdown discovery.

2. **Jalankan Skrip Testing Mandiri:**
   Tulis file implementasi menggunakan arsitektur clean proxy pattern:

```python
# Save as: test_runner.py
import asyncio
from edge_controller_lab import IndexationEngine, RequestContext, CanonicalDAGResolver

async def run_scenario_tests():
    dag = CanonicalDAGResolver()
    dag.add_edge("/products/clothing/men/jackets", "/products/jackets")
    engine = IndexationEngine(dag_resolver=dag)

    scenarios = [
        {
            "name": "E-Commerce Deep Facet Trap Check",
            "ctx": RequestContext(
                url="https://example.com/products/clothing/men/jackets?size=L&color=black&material=leather&sort=asc",
                user_agent="Googlebot",
                base_domain="example.com"
            ),
            "expected_robots": "noindex, follow",
            "expected_canonical": "https://example.com/products/jackets",
            "expected_status": 200
        },
        {
            "name": "AI Agent Clean Path Discovery",
            "ctx": RequestContext(
                url="https://example.com/products/jackets",
                user_agent="ClaudeBot",
                base_domain="example.com"
            ),
            "expected_robots": "index, follow",
            "expected_canonical": "https://example.com/products/jackets",
            "expected_status": 200
        }
    ]

    for sc in scenarios:
        res = engine.evaluate(sc["ctx"])
        print(f"Executing Test: {sc['name']}")
        assert res.status_code == sc["expected_status"], f"Status mismatch: {res.status_code} != {sc['expected_status']}"
        assert res.headers.get("X-Robots-Tag") == sc["expected_robots"], f"Robots mismatch: {res.headers.get('X-Robots-Tag')}"
        assert res.canonical_url == sc["expected_canonical"], f"Canonical mismatch: {res.canonical_url}"
        print(f"-> PASSED.")

if __name__ == "__main__":
    asyncio.run(run_scenario_tests())
```

3. **Verifikasi Output:**
   Jalankan pengujian untuk memastikan implementasi berjalan tanpa galat:
   ```bash
   python test_runner.py
   ```
   Output harus memvalidasi bahwa sistem secara otomatis mereduksi parameter terlarang, memutus siklus canonical via resolving DAG, serta menolak dan mengarahkan bot autonomous sesuai hak akses semantiknya tanpa menyentuh server database downstream.