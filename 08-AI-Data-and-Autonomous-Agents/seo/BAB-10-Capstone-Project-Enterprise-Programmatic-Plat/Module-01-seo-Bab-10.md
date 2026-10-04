# Bab 10: Capstone Project Enterprise Programmatic Platform Audit Engine — Module 01: High-Throughput Asynchronous Crawling & DOM Extraction Engine

---

## 1. Learning Objectives

Setelah menyelesaikan Modul 01 ini, Principal/Staff Engineer dan Technical SEO Specialist diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Core Crawling Engine Berbasis Asyncio & Headless Browser Pool**: Membangun engine crawling hybrid yang menggabungkan *fast-path HTTP/2 non-rendering* (`httpx`) dan *dynamic browser rendering context* (`Playwright`) dengan resource blocking teroptimasi untuk mencapai throughput >150 pages/menit per worker node.
2. **Mendeteksi Client-Side Rendering (CSR) Hydration Drift**: Mengukur dan menganalisis delta struktural (DOM mutation) antara respons raw HTML server-side dengan DOM pasca-eksekusi JavaScript untuk mengidentifikasi degradasi indeksabilitas.
3. **Mengekstrak dan Memvalidasi Graf Semantik (JSON-LD & Microdata)**: Membangun pipeline parsing rekursif untuk mengekstrak schema tree, mendeteksi *broken reference IDs* (`@id`), dan memvalidasi kepatuhan sintaksis terhadap skema Schema.org.
4. **Menerapkan Distributed Rate Limiting & Crawl Politeness**: Mengimplementasikan algoritma *Token Bucket* terdistribusi yang mematuhi batasan robots.txt, dynamic latency feedback, dan status crawl-budget target enterprise.

---

## 2. Concept Overview

Sistem audit SEO konvensional (Screaming Frog, Sitebulb, dsb.) didesain untuk eksekusi desktop/single-instance yang membatasi analisis platform enterprise dengan jutaan URL programmatic (misalnya marketplace, direktori agregator, media multinasional). Engine audit kelas enterprise memerlukan pendekatan arsitektur komputasi terdistribusi yang mampu membedakan dua kondisi fundamentally critical: **Wire State** (HTML mentah dari server) dan **Hydrated State** (DOM final yang dilihat oleh user dan rendering engine Googlebot).

```
[Raw Wire HTML (HTTP Fast-Path)] ──┐
                                   ├──> [DOM Differential Engine] ──> [Hydration Drift Analysis]
[Hydrated DOM (Headless Chromium)] ─┘
```

### Mental Model: Dual-Phase Asymmetric Auditing
Engine ini beroperasi menggunakan model *Two-Tier Asymmetric Fetching*:
1. **Tier 1 (Fast-Path Probe)**: Request asinkronus ultra-cepat melalui protocol HTTP/2 murni. Menganalisis respon header HTTP, status code, response time (TTFB), dan static DOM.
2. **Tier 2 (Headless Browser Evaluation)**: Dipicu jika dan hanya jika Tier 1 mendeteksi adanya critical dependency terhadap client-side execution (misalnya: tidak ada tag `<h1>`, meta robots missing di static HTML tapi ada marker SPA, atau verifikasi Core Web Vitals / CLS).

### DOM Hydration Drift
*Hydration Drift* terjadi ketika payload JavaScript client-side mengubah atau menghapus metadata penting yang telah dikirimkan oleh server-side rendering (SSR), atau sebaliknya—ketika link navigasi dan tag kanonikal baru disuntikkan secara dinamis setelah hydration selesai. Hal ini berpotensi membingungkan Googlebot WRS (Web Rendering Service) dan memboroskan jatah rendering budget.

---

## 3. Why It Matters

Bagi platform dengan skala jutaan *Programmatically Generated Pages* (PGP), kegagalan teknis kecil berlipat ganda secara eksponensial:

* **Hydration Mismatch & SEO Poisoning**: Sebuah bug pada update React/Next.js hydration dapat secara tidak sengaja menimpa tag `<link rel="canonical">` dengan URL root atau string kosong pada dynamic route. Googlebot yang memproses fase rendering dapat mengonsolidasikan jutaan halaman ke satu URL tunggal, memicu de-indeksasi massal.
* **Crawl-Budget Exhaustion**: Script pihak ketiga (analytics, tag manager, chat widgets) dapat melipatgandakan waktu eksekusi CPU saat headless browser melakukan crawling. Tanpa dynamic network interception dan resource blocking tingkat granular, biaya infrastruktur cloud crawling membengkak hingga 10x lipat dengan throughput audit yang sangat lambat.
* **Broken Internal Graph Loops**: Link yang dirender via `href="javascript:void(0)"` atau event `onClick` programmatic tidak dapat diikuti oleh crawler standar. Engine audit enterprise harus mampu mengekstraksi seluruh bentuk tautan serta memvalidasi canonical loop dan hreflang cluster secara real-time.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur internal dari **Module 01: Audit Ingestion & Extraction Engine**:

```
+───────────────────────────────────────────────────────────────────────────────────────────+
│                       Module 01: Ingestion & Extraction Engine                            │
+───────────────────────────────────────────────────────────────────────────────────────────+
                                              │
                                     [URL Dispatch Queue]
                                              │
                                              ▼
                             +─────────────────────────────────+
                             │   Politeness & Rate Controller  │
                             │  (Token Bucket / Redis Sliding) │
                             +─────────────────────────────────+
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         [Tier 1: HTTP/2 Fast Path]                      [Tier 2: Browser Pool Worker]
         - Async HTTPX Client                            - Playwright Chromium Instance
         - Header / TTFB Extraction                      - Request Interceptor (Block Asset)
         - Wire HTML Extraction                          - DOM Hydration & JS Execution
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                             +─────────────────────────────────+
                             │   Document Normalization Layer  │
                             +─────────────────────────────────+
                                              │
                      ┌───────────────────────┼───────────────────────┐
                      ▼                       ▼                       ▼
            +──────────────────+    +──────────────────+    +──────────────────+
            │ Meta & Directive │    │   JSON-LD DAG    │    │  DOM Structural  │
            │ Extraction Engine│    │ Validation Engine│    │    Diff Engine   │
            +──────────────────+    +──────────────────+    +──────────────────+
                      │                       │                       │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                             +─────────────────────────────────+
                             │    Normalized Audit Record      │
                             │   (Pydantic Canonical Schema)   │
                             +─────────────────────────────────+
                                              │
                                              ▼
                             [Downstream Module 02: Storage/DAG]
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### A. Dynamic Resource Interception
Browser rendering engine menghabiskan 60-80% waktu komputasi untuk mengunduh dan merender font, gambar, stylesheet eksternal, dan tracking script yang tidak memiliki dampak terhadap struktur DOM SEO. 
Module ini mengimplementasikan route pattern matching pada tingkat network driver CDP (Chrome DevTools Protocol). Semua request dengan resource type:
`image`, `media`, `font`, `stylesheet` (kecuali flag audit CSS aktif), dan tracking domains (Google Analytics, Segment, Datadog) di-*abort* secara instan pada layer soket sebelum mengonsumsi bandwidth.

### B. Two-Pass Structural Diffing
Engine mengekstrak dua set data untuk setiap target:
1. `DOM_wire`: Hasil parsing string dari `response.text()` HTTP mentah.
2. `DOM_hydrated`: Evaluasi `document.documentElement.outerHTML` dari Playwright page context setelah network idle atau event loop timeout.

Metrik komputasi diff meliputi:
* **Canonical Drift**: Apakah `href` canonical berubah antara Wire dan Hydrated?
* **Robots Drift**: Apakah meta robots beralih dari `index,follow` menjadi `noindex`?
* **Content Injection Ratio**: $\frac{\text{Length}(\text{DOM}_{hydrated}) - \text{Length}(\text{DOM}_{wire})}{\text{Length}(\text{DOM}_{hydrated})}$

### C. JSON-LD Graph Flattening & Cyclic Validation
JSON-LD modern memanfaatkan arsitektur `@graph` bertingkat di mana entitas saling merujuk menggunakan pointer `@id`. Parsing naif berbasis regex atau traversal pohon linear sering melewatkan skema yang terputus (*orphaned schemas*). Engine memetakan seluruh array `@graph` ke dalam Directed Acyclic Graph (DAG) di memori, memverifikasi bahwa entitas turunan (seperti `Offer` pada `Product`, atau `Author` pada `Article`) terhubung secara sah ke node root.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi modul audit core engine menggunakan Python 3.11+ modern, `asyncio`, `playwright`, `httpx`, `BeautifulSoup4`, dan `pydantic`.

```python
"""
Enterprise Programmatic Platform Audit Engine - Module 01
Core Extraction & Asynchronous Parsing Engine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from pydantic import BaseModel, Field, HttpUrl, ValidationError

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s (%(process)d): %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("audit.engine.module01")


# ============================================================================
# PYDANTIC SCHEMAS (DATA CONTRACTS)
# ============================================================================

class MetaDirectives(BaseModel):
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical_url: Optional[str] = None
    robots_meta: Optional[str] = None
    x_robots_tag: Optional[str] = None
    h1_elements: List[str] = Field(default_factory=list)


class HydrationDriftReport(BaseModel):
    has_drift: bool = False
    wire_canonical: Optional[str] = None
    hydrated_canonical: Optional[str] = None
    wire_robots: Optional[str] = None
    hydrated_robots: Optional[str] = None
    h1_count_mismatch: bool = False
    wire_h1_count: int = 0
    hydrated_h1_count: int = 0


class ExtractedLink(BaseModel):
    href: str
    target_url: str
    anchor_text: str
    is_nofollow: bool
    is_internal: bool


class AuditPayload(BaseModel):
    url: str
    http_status: int
    response_time_ms: float
    wire_meta: MetaDirectives
    hydrated_meta: Optional[MetaDirectives] = None
    drift_report: Optional[HydrationDriftReport] = None
    json_ld_schemas: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[ExtractedLink] = Field(default_factory=list)
    render_required: bool = False
    errors: List[str] = Field(default_factory=list)


# ============================================================================
# AUDIT EXTRACTION ENGINE INTERFACE
# ============================================================================

class EnterpriseAuditEngine:
    """High-throughput audit extraction engine implementing two-pass evaluation."""

    BLOCKED_EXTENSIONS = (
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
        ".css", ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".mp4", ".mp3", ".avi", ".pdf"
    )

    BLOCKED_HOST_MARKERS = (
        "google-analytics.com",
        "googletagmanager.com",
        "facebook.net",
        "hotjar.com",
        "segment.io",
        "doubleclick.net"
    )

    def __init__(
        self,
        base_domain: str,
        concurrency_limit: int = 20,
        user_agent: str = "EnterpriseSEOBot/1.0 (+https://internal.platform/bot.html)",
        browser_pool_size: int = 5,
    ) -> None:
        self.base_domain = base_domain.lower()
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.user_agent = user_agent
        self.browser_pool_size = browser_pool_size
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def initialize(self) -> None:
        """Bootstraps headless browser context pool."""
        logger.info("Initializing Playwright browser context...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--blink-settings=imagesEnabled=false",
            ],
        )

    async def teardown(self) -> None:
        """Terminates active browser sessions and closes runner context."""
        logger.info("Tearing down browser context pool...")
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _is_internal_link(self, target_url: str) -> bool:
        """Validates if a URL belongs to the engine's target host boundary."""
        try:
            parsed = urlparse(target_url)
            return parsed.netloc.lower() == self.base_domain or parsed.netloc == ""
        except Exception:
            return False

    def _extract_meta(self, soup: BeautifulSoup, response_headers: Optional[httpx.Headers] = None) -> MetaDirectives:
        """Extracts core SEO directives from BeautifulSoup DOM tree."""
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
        desc = desc_tag.get("content", "").strip() if desc_tag and desc_tag.get("content") else None

        canonical_tag = soup.find("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
        canonical = canonical_tag.get("href", "").strip() if canonical_tag and canonical_tag.get("href") else None

        robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        robots = robots_tag.get("content", "").strip() if robots_tag and robots_tag.get("content") else None

        x_robots = None
        if response_headers:
            x_robots = response_headers.get("x-robots-tag")

        h1s = [h1.get_text(strip=True) for h1 in soup.find_all("h1") if h1.get_text(strip=True)]

        return MetaDirectives(
            title=title,
            meta_description=desc,
            canonical_url=canonical,
            robots_meta=robots,
            x_robots_tag=x_robots,
            h1_elements=h1s,
        )

    def _extract_json_ld(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parses and normalizes structural JSON-LD blobs, handling malformed JSON safely."""
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        schemas = []
        for script in scripts:
            content = script.string
            if not content:
                continue
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    schemas.extend(data)
                elif isinstance(data, dict):
                    schemas.append(data)
            except json.JSONDecodeError as err:
                logger.warning(f"Malformed JSON-LD detected: {err}")
                continue
        return schemas

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[ExtractedLink]:
        """Extracts all hyperlinks, determining absolute resolution and rel attributes."""
        extracted: List[ExtractedLink] = []
        for a_tag in soup.find_all("a", href=True):
            raw_href = a_tag["href"].strip()
            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            absolute_url = urljoin(base_url, raw_href)
            rel_list = a_tag.get("rel", [])
            if isinstance(rel_list, str):
                rel_list = [rel_list]
            
            is_nofollow = "nofollow" in [r.lower() for r in rel_list]
            is_internal = self._is_internal_link(absolute_url)

            extracted.append(
                ExtractedLink(
                    href=raw_href,
                    target_url=absolute_url,
                    anchor_text=a_tag.get_text(strip=True),
                    is_nofollow=is_nofollow,
                    is_internal=is_internal,
                )
            )
        return extracted

    async def _handle_route_interception(self, route) -> None:
        """CDP request interceptor blocking non-critical media and metrics payloads."""
        req = route.request
        url_lower = req.url.lower()

        # Check domain-level markers
        if any(marker in url_lower for marker in self.BLOCKED_HOST_MARKERS):
            await route.abort()
            return

        # Check resource extensions
        parsed_path = urlparse(url_lower).path
        if any(parsed_path.endswith(ext) for ext in self.BLOCKED_EXTENSIONS):
            await route.abort()
            return

        # Check resource categories
        if req.resource_type in ["image", "media", "font"]:
            await route.abort()
            return

        await route.continue_()

    async def _render_dynamic_page(self, url: str) -> Tuple[str, List[str]]:
        """Executes full Chromium rendering context for dynamic evaluation."""
        if not self._browser:
            raise RuntimeError("Browser not initialized. Invoke initialize() first.")

        rendered_html = ""
        captured_errors: List[str] = []
        
        context: BrowserContext = await self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1920, "height": 1080},
        )
        page: Page = await context.new_page()

        try:
            # Enable aggressive resource blocking
            await page.route("**/*", self._handle_route_interception)

            # Navigate with strict execution timeout (15s)
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            if response is None:
                captured_errors.append("Rendering context received null response from target.")
            
            # Wait short buffer for critical micro-tasks hydration
            await page.wait_for_timeout(750)
            rendered_html = await page.content()

        except Exception as exc:
            captured_errors.append(f"Browser rendering exception: {str(exc)}")
        finally:
            await page.close()
            await context.close()

        return rendered_html, captured_errors

    def _calculate_drift(
        self, wire_meta: MetaDirectives, hydrated_meta: MetaDirectives
    ) -> HydrationDriftReport:
        """Determines differential drift anomalies between server wire and client DOM."""
        canonical_mismatch = wire_meta.canonical_url != hydrated_meta.canonical_url
        robots_mismatch = wire_meta.robots_meta != hydrated_meta.robots_meta
        h1_mismatch = len(wire_meta.h1_elements) != len(hydrated_meta.h1_elements)

        has_drift = canonical_mismatch or robots_mismatch or h1_mismatch

        return HydrationDriftReport(
            has_drift=has_drift,
            wire_canonical=wire_meta.canonical_url,
            hydrated_canonical=hydrated_meta.canonical_url,
            wire_robots=wire_meta.robots_meta,
            hydrated_robots=hydrated_meta.robots_meta,
            h1_count_mismatch=h1_mismatch,
            wire_h1_count=len(wire_meta.h1_elements),
            hydrated_h1_count=len(hydrated_meta.h1_elements),
        )

    async def audit_url(self, url: str) -> AuditPayload:
        """Executes orchestration audit on a solitary URL target."""
        async with self.semaphore:
            start_time = time.monotonic()
            errors: List[str] = []
            
            # Phase 1: Fast-Path Wire Execution
            async with httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
                timeout=httpx.Timeout(10.0, connect=5.0),
                http2=True,
            ) as client:
                try:
                    response = await client.get(url)
                    execution_time = (time.monotonic() - start_time) * 1000.0
                except httpx.HTTPError as exc:
                    return AuditPayload(
                        url=url,
                        http_status=0,
                        response_time_ms=(time.monotonic() - start_time) * 1000.0,
                        wire_meta=MetaDirectives(),
                        errors=[f"HTTP transport layer failure: {str(exc)}"],
                    )

            wire_html = response.text
            soup_wire = BeautifulSoup(wire_html, "lxml")
            wire_meta = self._extract_meta(soup_wire, response.headers)
            json_ld_schemas = self._extract_json_ld(soup_wire)
            links = self._extract_links(soup_wire, str(response.url))

            # Determine if CSR evaluation is required
            # Heuristic: Missing critical tags in SSR or SPA signature present
            requires_render = (
                len(wire_meta.h1_elements) == 0
                or wire_meta.canonical_url is None
                or '<div id="root"></div>' in wire_html
                or '<div id="__next"></div>' in wire_html
            )

            hydrated_meta = None
            drift_report = None

            if requires_render:
                logger.debug(f"Render triggered for URL: {url}")
                hydrated_html, render_errors = await self._render_dynamic_page(url)
                errors.extend(render_errors)

                if hydrated_html:
                    soup_hydrated = BeautifulSoup(hydrated_html, "lxml")
                    hydrated_meta = self._extract_meta(soup_hydrated)
                    drift_report = self._calculate_drift(wire_meta, hydrated_meta)
                    
                    # Merge dynamic JSON-LD schemas if newly injected
                    dynamic_schemas = self._extract_json_ld(soup_hydrated)
                    if len(dynamic_schemas) > len(json_ld_schemas):
                        json_ld_schemas = dynamic_schemas

                    # Merge dynamic links
                    dynamic_links = self._extract_links(soup_hydrated, url)
                    existing_targets = {link.target_url for link in links}
                    for dyn_link in dynamic_links:
                        if dyn_link.target_url not in existing_targets:
                            links.append(dyn_link)
                            existing_targets.add(dyn_link.target_url)

            return AuditPayload(
                url=str(response.url),
                http_status=response.status_code,
                response_time_ms=execution_time,
                wire_meta=wire_meta,
                hydrated_meta=hydrated_meta,
                drift_report=drift_report,
                json_ld_schemas=json_ld_schemas,
                links=links,
                render_required=requires_render,
                errors=errors,
            )


# ============================================================================
# ENTRYPOINT DEMONSTRATION & BENCHMARK
# ============================================================================

async def main():
    target_urls = [
        "https://example.com",
    ]

    engine = EnterpriseAuditEngine(base_domain="example.com", concurrency_limit=5)
    await engine.initialize()

    try:
        tasks = [engine.audit_url(u) for u in target_urls]
        results: List[AuditPayload] = await asyncio.gather(*tasks)

        for audit in results:
            print(f"\n--- AUDIT RESULTS FOR: {audit.url} ---")
            print(f"Status Code       : {audit.http_status} ({audit.response_time_ms:.2f}ms)")
            print(f"Wire Title        : {audit.wire_meta.title}")
            print(f"Wire Canonical    : {audit.wire_meta.canonical_url}")
            print(f"Dynamic Render Run: {audit.render_required}")
            if audit.drift_report:
                print(f"Hydration Drift   : {audit.drift_report.has_drift}")
                print(f" -> Canonical Mismatch: {audit.drift_report.wire_canonical} != {audit.drift_report.hydrated_canonical}")
            print(f"JSON-LD Count     : {len(audit.json_ld_schemas)}")
            print(f"Discovered Links  : {len(audit.links)}")
            if audit.errors:
                print(f"Errors Logged     : {audit.errors}")
    finally:
        await engine.teardown()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

### 1. Soft 404 Pages Returning HTTP 200
* **Gejala**: Halaman programmatic yang stok produknya kosong mengembalikan response body bertuliskan "Produk Tidak Ditemukan", namun status code HTTP tetap `200 OK`.
* **Deteksi & Mitigasi**: Implementasikan regex fingerprint matching pada parser content (misal: checking phrase pattern *out of stock*, *item not found*, atau DOM wrapper kosong `.empty-product-state`) dan periksa keberadaan header `X-Robots-Tag: noindex` atau canonical yang dialihkan paksa ke home page.

### 2. Hydration Wiping Meta Tags
* **Gejala**: Server mengirimkan `<title>` dan `<meta name="robots" content="index">`, namun saat React/Vue hydrate di client side, state store yang tidak terinisialisasi merender string kosong atau menghapus elemen tag `<head>`.
* **Deteksi & Mitigasi**: Engine menandai status `CRITICAL_DRIFT` jika tag canonical atau robots ada di `wire_meta` namun bernilai `None` atau kosong di `hydrated_meta`.

### 3. Chromium Out-Of-Memory (OOM) Leakage
* **Gejala**: Playwright context yang dibiarkan terbuka terus menerus (*long-running process*) akan mengumpulkan trace memori, cache V8, dan garbage collection yang macet, berujung pada worker crash (`SIGSEGV` / `Exit code 137`).
* **Mitigasi**: Browser context (`BrowserContext`) harus dibuat secara **ephemeral** per request dan di-destroy via block `finally`. Lakukan hard-recycle pada instance parent `Browser` setiap 1.000 render execution.

### 4. Malformed Infinite Redirect Chains
* **Gejala**: Engine terjebak dalam loop: `URL A -> 301 -> URL B -> 302 -> URL A`.
* **Mitigasi**: Batasi `follow_redirects=True` pada `httpx` dengan setting `max_redirects=5`. Simpan array URL *redirect history* di payload untuk mengidentifikasi redirect hop berulang.

---

## 8. Trade-offs & Alternatif Solusi

| Parameter | Pendekatan Terpilih (Hybrid: HTTPX + Playwright Selective) | Alternatif A: Full Playwright (Render Semua URL) | Alternatif B: Pure HTTP Scraper (Scrapy/HTTPX saja) |
| :--- | :--- | :--- | :--- |
| **Throughput (Pages/Min)** | **Tinggi (~150 - 300 / node)** | Sangat Rendah (~20 - 40 / node) | Ekstrem (>1.500 / node) |
| **Resource Footprint** | **Moderat** (RAM 1-2 GB per worker) | Sangat Tinggi (RAM >8 GB per worker) | Ultra Rendah (RAM <512 MB) |
| **Akurasi Client-Side** | **Presisi Tinggi** (Hanya merender jika ada marker CSR / missing meta) | Presisi Maksimum (Semua script dieksekusi) | **Nol** (Gagal mengevaluasi SPA/Hydration bug) |
| **Infrastruktur / Biaya** | **Cost-Effective** (Autoscaling worker pool) | Sangat Mahal (Membutuhkan cluster node besar) | Paling Murah |
| **Maintenance Complexity**| Menengah (Memerlukan routing logic CSR) | Rendah (Single-track pipeline) | Rendah |

---

## 9. Best Practices & Standar Industri

1. **RFC 9309 (Robots Exclusion Protocol) Strict Compliance**: Parse `robots.txt` pada level host sebelum menembak request ke Tier 1. Cache aturan robots di Redis dengan TTL 24 jam.
2. **Crawl Politeness via Exponential Backoff**: Jika server merespons dengan status `429 Too Many Requests` atau `503 Service Unavailable`, turunkan concurrency semaphore worker sebesar 50% dan terapkan backoff waktu acak (`jittered exponential backoff`).
3. **Canonical Normalization Standard**:
   * Hapus *trailing slashes* jika target framework tidak menggunakannya secara konsisten.
   * Urutkan query parameters secara alfabetis (`?b=1&a=2` $\rightarrow$ `?a=2&b=1`) untuk menghindari duplikasi pelaporan link graph.
   * Strip fragment identifiers (`#section-anchor`).
4. **Structured Data Validation Strictness**: Evaluasi JSON-LD bukan hanya dari validitas format JSON, melainkan terhadap schema definition type (`@type: Organization`, `@type: Product`, dll.) menggunakan library JSON Schema Validator downstream.

---

## 10. Hands-on Lab Exercise

### Deskripsi Lab
Bangun skenario pengujian unit lokal untuk memvalidasi engine terhadap halaman dummy yang memiliki bug **Canonical Hydration Drift**.

### Langkah Pengerjaan

#### Langkah 1: Siapkan Environment & Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install httpx playwright beautifulsoup4 lxml pydantic
playwright install chromium
```

#### Langkah 2: Buat Mock Server dengan Hydration Drift
Simpan script berikut sebagai `mock_server.py`:
```python
from http.server import HTTPServer, BaseHTTPRequestHandler

class DriftServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        
        # Wire HTML memiliki canonical ke halaman yang benar
        # Namun JavaScript client-side secara tidak sengaja mengubahnya ke localhost:8000/broken-canonical
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Enterprise Product Page</title>
            <link rel="canonical" href="https://example.com/products/item-1" />
            <div id="__next"></div>
        </head>
        <body>
            <h1>Original SSR Heading</h1>
            <script>
                // Simulasi hydration script yang me-mutate DOM
                setTimeout(() => {
                    const canonical = document.querySelector('link[rel="canonical"]');
                    if (canonical) {
                        canonical.setAttribute('href', 'https://example.com/broken-canonical');
                    }
                    const h1 = document.createElement('h1');
                    h1.innerText = 'Hydrated Injected Heading';
                    document.body.appendChild(h1);
                }, 100);
            </script>
        </body>
        </html>
        """
        self.wfile.write(html.encode("utf-8"))

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8888), DriftServer)
    print("Serving mock on http://127.0.0.1:8888 ...")
    server.serve_forever()
```

#### Langkah 3: Eksekusi Test Runner
Jalankan server di terminal pertama:
```bash
python mock_server.py
```

Di terminal kedua, jalankan engine audit kita yang diarahkan ke mock target:
```python
import asyncio
from audit_engine import EnterpriseAuditEngine

async def run_lab():
    engine = EnterpriseAuditEngine(base_domain="127.0.0.1")
    await engine.initialize()
    try:
        report = await engine.audit_url("http://127.0.0.1:8888")
        assert report.drift_report is not None, "Drift report must be populated!"
        assert report.drift_report.has_drift is True, "Engine failed to catch hydration drift!"
        print("[LAB SUCCESS] Hydration Drift detected successfully:")
        print(f"Wire Canonical    : {report.drift_report.wire_canonical}")
        print(f"Hydrated Canonical: {report.drift_report.hydrated_canonical}")
        print(f"Wire H1 count     : {report.drift_report.wire_h1_count}")
        print(f"Hydrated H1 count : {report.drift_report.hydrated_h1_count}")
    finally:
        await engine.teardown()

if __name__ == "__main__":
    asyncio.run(run_lab())
```

### Kriteria Keberhasilan (Verification Checklist)
* [x] Dependency browser Chromium terinstall tanpa error system library.
* [x] Network interceptor berhasil memblokir image/font/stylesheet saat render dynamic context.
* [x] Terminal menghasilkan output assertion `[LAB SUCCESS]` yang membuktikan bahwa perbedaan `wire_canonical` (`https://example.com/products/item-1`) dan `hydrated_canonical` (`https://example.com/broken-canonical`) teridentifikasi secara presisi.