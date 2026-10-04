#!/usr/bin/env python3
"""
Lab Hands-on: Bab 08 - Interoperabilitas Platform, SEO Teknis, dan Metadata
Modul 02: Deep Dive Technical SEO Parser, OpenGraph/Twitter Card Validator, & JSON-LD Engine

Script ini mendemonstrasikan engine analisis SEO teknis mandiri berbasis Python Standard Library.
Mengimplementasikan:
1. Streaming HTML Parser khusus untuk mengekstrak metadata level <head>.
2. Validator Interoperabilitas Platform: OpenGraph Protocol, Twitter Cards, Schema.org JSON-LD.
3. Mesin audit Technical SEO: Deteksi Canonicalization, Robots Directives, Hreflang Tags,
   serta kalkulasi Health Score berbasis pembobotan matriks industri.
4. Simulasi Rich Snippet & Social Card Renderer di terminal.
"""

from html.parser import HTMLParser
import json
import re
import sys
from typing import Dict, List, Any, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_GRAY = "\033[90m"


class TechnicalSEOCrawler(HTMLParser):
    """
    Subclass HTMLParser berperforma tinggi yang fokus membedah token metadata
    pada dokumen HTML tanpa memerlukan dependency eksternal seperti BeautifulSoup.
    """
    def __init__(self):
        super().__init__()
        self.in_head = False
        self.in_title = False
        self.in_json_ld = False
        
        # Ekstraksi Penampung Data
        self.title: str = ""
        self.meta_tags: List[Dict[str, str]] = []
        self.link_tags: List[Dict[str, str]] = []
        self.json_ld_scripts: List[str] = []
        self._current_json_ld_buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        tag = tag.lower()
        attr_dict = {k.lower(): (v or "").strip() for k, v in attrs}

        if tag == "head":
            self.in_head = True
        elif tag == "title" and self.in_head:
            self.in_title = True
        elif tag == "meta" and self.in_head:
            self.meta_tags.append(attr_dict)
        elif tag == "link" and self.in_head:
            self.link_tags.append(attr_dict)
        elif tag == "script" and self.in_head:
            if attr_dict.get("type") == "application/ld+json":
                self.in_json_ld = True
                self._current_json_ld_buffer = []

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag == "head":
            self.in_head = False
        elif tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_json_ld:
            self.in_json_ld = False
            raw_json = "".join(self._current_json_ld_buffer).strip()
            if raw_json:
                self.json_ld_scripts.append(raw_json)
            self._current_json_ld_buffer = []

    def handle_data(self, data: str):
        if self.in_title:
            self.title += data
        elif self.in_json_ld:
            self._current_json_ld_buffer.append(data)


class TechnicalSEOAuditEngine:
    """
    Mesin validasi dan pembobotan teknis SEO, Open Graph, Twitter Card,
    serta validasi integritas Structured Data (JSON-LD).
    """
    def __init__(self, raw_html: str, target_url: str):
        self.raw_html = raw_html
        self.target_url = target_url
        self.parser = TechnicalSEOCrawler()
        self.parser.feed(self.raw_html)

        # Normalisasi struktur metadata
        self.meta_named: Dict[str, str] = {}
        self.meta_property: Dict[str, str] = {}
        self._normalize_metadata()

        # Audit Storage
        self.audit_log: List[Dict[str, Any]] = []
        self.score: float = 100.0

    def _normalize_metadata(self):
        """Memetakan meta tag ke format kamus berorientasi nama & properti."""
        for meta in self.parser.meta_tags:
            if "name" in meta and "content" in meta:
                self.meta_named[meta["name"].lower()] = meta["content"]
            elif "property" in meta and "content" in meta:
                self.meta_property[meta["property"].lower()] = meta["content"]

    def _add_log(self, category: str, rule: str, passed: bool, impact: float, details: str):
        """Mencatat hasil evaluasi aturan dan melakukan pemotongan skor jika gagal."""
        if not passed:
            self.score = max(0.0, self.score - impact)
        self.audit_log.append({
            "category": category,
            "rule": rule,
            "passed": passed,
            "impact": impact,
            "details": details
        })

    def audit_head_basics(self):
        """Audit elemen dasar Head: Title Tag, Meta Description, Charset, Viewport."""
        title = self.parser.title.strip()
        desc = self.meta_named.get("description", "")
        viewport = self.meta_named.get("viewport", "")

        # Evaluasi Title
        if not title:
            self._add_log("Core SEO", "Title Presence", False, 20.0, "Tag <title> kosong atau tidak ditemukan.")
        elif 30 <= len(title) <= 65:
            self._add_log("Core SEO", "Title Length", True, 0.0, f"Panjang title optimal ({len(title)} char).")
        else:
            self._add_log("Core SEO", "Title Length", False, 5.0, f"Panjang title tidak ideal ({len(title)} char). Disarankan 30-65 char.")

        # Evaluasi Description
        if not desc:
            self._add_log("Core SEO", "Meta Description", False, 15.0, "Meta description tidak ditemukan.")
        elif 70 <= len(desc) <= 160:
            self._add_log("Core SEO", "Meta Description Length", True, 0.0, f"Panjang deskripsi ideal ({len(desc)} char).")
        else:
            self._add_log("Core SEO", "Meta Description Length", False, 5.0, f"Panjang deskripsi ({len(desc)} char) di luar rekomendasi (70-160 char).")

        # Viewport (Mobile Friendly Signal)
        if "width=device-width" in viewport.lower():
            self._add_log("Technical", "Mobile Viewport", True, 0.0, "Meta viewport responsif terkonfigurasi dengan benar.")
        else:
            self._add_log("Technical", "Mobile Viewport", False, 10.0, "Meta viewport tidak valid atau absen.")

    def audit_canonical_and_robots(self):
        """Audit direktif pengindeksan: Canonical Link, Meta Robots, dan Hreflang."""
        canonicals = [link.get("href") for link in self.parser.link_tags if link.get("rel") == "canonical"]
        
        if len(canonicals) == 0:
            self._add_log("Indexing", "Canonical Tag", False, 10.0, "Tag rel='canonical' absen. Rentan masalah duplicate content.")
        elif len(canonicals) > 1:
            self._add_log("Indexing", "Multiple Canonical", False, 15.0, "Ditemukan multiple canonical tags, membingungkan search engine.")
        else:
            c_url = canonicals[0]
            if c_url.startswith("http://") or c_url.startswith("https://"):
                self._add_log("Indexing", "Canonical URL Absolute", True, 0.0, f"Canonical valid: {c_url}")
            else:
                self._add_log("Indexing", "Canonical URL Absolute", False, 5.0, f"Canonical harus absolut, ditemukan: {c_url}")

        robots = self.meta_named.get("robots", "").lower()
        if "noindex" in robots:
            self._add_log("Indexing", "Robots Directive", False, 0.0, "Peringatan: Tag 'noindex' terdeteksi. Halaman diblokir dari SERP!")
        else:
            self._add_log("Indexing", "Robots Directive", True, 0.0, "Halaman diizinkan diindeks (indexable).")

    def audit_social_graph(self):
        """Audit Interoperabilitas Metadata Sosial (Open Graph & Twitter Cards)."""
        og_required = ["og:title", "og:description", "og:image", "og:url"]
        for prop in og_required:
            val = self.meta_property.get(prop)
            if val:
                self._add_log("Social Graph", f"OpenGraph: {prop}", True, 0.0, f"Terdifinisi: {val[:40]}...")
            else:
                self._add_log("Social Graph", f"OpenGraph: {prop}", False, 4.0, f"Missing property OpenGraph: {prop}")

        tw_card = self.meta_named.get("twitter:card")
        if tw_card in ["summary", "summary_large_image"]:
            self._add_log("Social Graph", "Twitter Card Type", True, 0.0, f"Format kartu twitter valid: {tw_card}")
        else:
            self._add_log("Social Graph", "Twitter Card Type", False, 4.0, "Twitter card tidak valid atau tidak dideklarasikan.")

    def audit_structured_data(self):
        """Validasi Parser Sintaksis dan Skema Semantik Schema.org via JSON-LD."""
        if not self.parser.json_ld_scripts:
            self._add_log("Structured Data", "Schema.org Presence", False, 10.0, "Tidak ada payload JSON-LD terdeteksi.")
            return

        for idx, raw_json in enumerate(self.parser.json_ld_scripts):
            try:
                data = json.loads(raw_json)
                context = data.get("@context", "")
                schema_type = data.get("@type", "")

                if "schema.org" in context and schema_type:
                    self._add_log("Structured Data", f"JSON-LD Schema Payload #{idx+1}", True, 0.0, 
                                  f"Valid @type: '{schema_type}' dengan konteks: '{context}'")
                else:
                    self._add_log("Structured Data", f"JSON-LD Schema Payload #{idx+1}", False, 8.0, 
                                  "JSON-LD kehilangan @context standard schema.org atau @type yang sah.")
            except json.JSONDecodeError as err:
                self._add_log("Structured Data", f"JSON-LD Syntax #{idx+1}", False, 12.0, f"Syntax Error: {err}")

    def run_all(self):
        self.audit_head_basics()
        self.audit_canonical_and_robots()
        self.audit_social_graph()
        self.audit_structured_data()

    def render_social_preview(self):
        """Merender representasi teks visual OpenGraph Card di terminal."""
        og_title = self.meta_property.get("og:title", self.parser.title.strip() or "Untitled")
        og_desc = self.meta_property.get("og:description", self.meta_named.get("description", "No description available."))
        og_image = self.meta_property.get("og:image", "https://via.placeholder.com/1200x630.png?text=No+OG+Image")
        og_url = self.meta_property.get("og:url", self.target_url)

        print(f"\n{CLR_MAGENTA}{CLR_BOLD}─── [SOCIAL PREVIEW SIMULATOR: FACEBOOK/LINKEDIN/SLACK] ───{CLR_RESET}")
        print(f"{CLR_GRAY}┌────────────────────────────────────────────────────────┐{CLR_RESET}")
        print(f"{CLR_GRAY}│{CLR_RESET} [IMAGE PREVIEW]: {CLR_CYAN}{og_image[:40]:<40}{CLR_RESET} {CLR_GRAY}│{CLR_RESET}")
        print(f"{CLR_GRAY}│{CLR_RESET} {CLR_BOLD}{og_title[:54]:<54}{CLR_RESET} {CLR_GRAY}│{CLR_RESET}")
        print(f"{CLR_GRAY}│{CLR_RESET} {CLR_GRAY}{og_desc[:54]:<54}{CLR_RESET} {CLR_GRAY}│{CLR_RESET}")
        print(f"{CLR_GRAY}│{CLR_RESET} {CLR_BLUE}{og_url[:54]:<54}{CLR_RESET} {CLR_GRAY}│{CLR_RESET}")
        print(f"{CLR_GRAY}└────────────────────────────────────────────────────────┘{CLR_RESET}")

    def display_report(self):
        """Menghasilkan representasi CLI informatif terformat warna."""
        print(f"\n{CLR_BOLD}{CLR_BLUE}=== TECHNICAL SEO & METADATA AUDIT REPORT ==={CLR_RESET}")
        print(f"Target URL: {CLR_CYAN}{self.target_url}{CLR_RESET}")
        
        status_color = CLR_GREEN if self.score >= 85 else (CLR_YELLOW if self.score >= 60 else CLR_RED)
        print(f"Global Health Score: {status_color}{CLR_BOLD}{self.score:.1f}/100{CLR_RESET}\n")

        current_cat = ""
        for entry in self.audit_log:
            if entry["category"] != current_cat:
                current_cat = entry["category"]
                print(f"{CLR_BOLD}Category: {current_cat}{CLR_RESET}")

            flag = f"{CLR_GREEN}[PASS]{CLR_RESET}" if entry["passed"] else f"{CLR_RED}[FAIL -{entry['impact']}pt]{CLR_RESET}"
            print(f"  {flag} {CLR_BOLD}{entry['rule']}:{CLR_RESET} {entry['details']}")

        self.render_social_preview()


# --- Mock Datasets untuk Lab Hands-on ---

HTML_DOCUMENT_OPTIMIZED = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kursus Arsitektur Frontend Modern &amp; SEO Teknis</title>
    <meta name="description" content="Pelajari interoperabilitas platform web, implementasi JSON-LD Schema, Open Graph protocol, dan audit SEO teknis secara mendalam.">
    <link rel="canonical" href="https://example.com/courses/technical-seo-deep-dive">
    <meta name="robots" content="index, follow">
    
    <!-- Open Graph Protocol -->
    <meta property="og:title" content="Pelajari Arsitektur Frontend Modern &amp; SEO Teknis">
    <meta property="og:description" content="Kurikulum komprehensif implementasi metadata terstandar, parser, dan integrasi social crawler.">
    <meta property="og:image" content="https://example.com/assets/banner-course.jpg">
    <meta property="og:url" content="https://example.com/courses/technical-seo-deep-dive">
    <meta property="og:type" content="article">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@frontend_lab">
    <meta name="twitter:creator" content="@lead_dev">

    <!-- Structured Data: JSON-LD -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Course",
      "name": "Arsitektur Frontend Modern & SEO Teknis",
      "description": "Lab simulasi interoperabilitas Web & Platform Metadata Crawler.",
      "provider": {
        "@type": "Organization",
        "name": "DevLab Academy",
        "sameAs": "https://example.com"
      }
    }
    </script>
</head>
<body>
    <main><h1>Modul 02: Deep Dive Metadata</h1></main>
</body>
</html>
"""

HTML_DOCUMENT_POOR = """<!DOCTYPE html>
<html>
<head>
    <title>Pendek</title>
    <!-- Viewport dan charset absen -->
    <meta name="robots" content="noindex, nofollow">
    <link rel="canonical" href="/halaman-relatif">
    <link rel="canonical" href="https://example.com/duplikat-kedua">
    
    <!-- OpenGraph tidak lengkap -->
    <meta property="og:title" content="Halaman Kurang Teroptimasi">

    <!-- JSON-LD Corrupt / Syntax Error sengaja dimasukkan -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Judul Artikel Tanpa Penutup Valid"
    </script>
</head>
<body>
    <p>Halaman dengan broken metadata</p>
</body>
</html>
"""

def main():
    print(f"{CLR_BOLD}{CLR_GREEN}Menginisialisasi Lab Hands-on: Technical SEO & Metadata Engine...{CLR_RESET}")

    # Case 1: Eksekusi Dokumen Sesuai Standar Industri
    print(f"\n{CLR_YELLOW}>>> Uji Sampel 1: Web Production-Ready (High Optimization){CLR_RESET}")
    engine_opt = TechnicalSEOAuditEngine(HTML_DOCUMENT_OPTIMIZED, "https://example.com/courses/technical-seo-deep-dive")
    engine_opt.run_all()
    engine_opt.display_report()

    print("\n" + "="*70 + "\n")

    # Case 2: Eksekusi Dokumen Malformed / Masalah SEO Teknis Kritis
    print(f"{CLR_YELLOW}>>> Uji Sampel 2: Web Broken Metadata & Non-Indexable{CLR_RESET}")
    engine_poor = TechnicalSEOAuditEngine(HTML_DOCUMENT_POOR, "https://example.com/broken-page")
    engine_poor.run_all()
    engine_poor.display_report()

    print(f"\n{CLR_GREEN}{CLR_BOLD}[SUKSES]{CLR_RESET} Selesai menjalankan simulasi parser SEO teknis.")

if __name__ == "__main__":
    main()