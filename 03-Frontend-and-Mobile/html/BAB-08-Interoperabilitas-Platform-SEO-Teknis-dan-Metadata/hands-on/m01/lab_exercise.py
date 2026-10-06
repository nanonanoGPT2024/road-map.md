#!/usr/bin/env python3
"""
Lab Exercise: Technical SEO & Metadata Interoperability Engine
BAB 08: Interoperabilitas Platform, SEO Teknis, dan Metadata HTML
Mendemonstrasikan validasi metadata Open Graph, Twitter Cards, JSON-LD,
Canonical Links, Robots Directives, dan Alternates secara interaktif.
"""

import sys
import json
import re
from html.parser import HTMLParser
from typing import Dict, List, Any, Optional

# ANSI Color Codes for Terminal UI
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_MAGENTA = "\033[35m"
COLOR_CYAN = "\033[36m"
COLOR_GRAY = "\033[90m"


class MetadataExtractor(HTMLParser):
    """HTML Parser khusus untuk mengekstrak elemen metadata SEO & Open Graph."""

    def __init__(self):
        super().__init__()
        self.title: Optional[str] = None
        self.in_title: bool = False
        self.meta_tags: List[Dict[str, str]] = []
        self.link_tags: List[Dict[str, str]] = []
        self.json_ld_scripts: List[str] = []
        self.in_json_ld: bool = False
        self._current_script_buf: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        attr_dict = {k.lower(): v for k, v in attrs if v is not None}

        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.meta_tags.append(attr_dict)
        elif tag == "link":
            self.link_tags.append(attr_dict)
        elif tag == "script":
            script_type = attr_dict.get("type", "").lower()
            if script_type == "application/ld+json":
                self.in_json_ld = True
                self._current_script_buf = []

    def handle_endtag(self, tag: str):
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_json_ld:
            self.in_json_ld = False
            raw_json = "".join(self._current_script_buf).strip()
            if raw_json:
                self.json_ld_scripts.append(raw_json)

    def handle_data(self, data: str):
        if self.in_title:
            self.title = (self.title or "") + data
        elif self.in_json_ld:
            self._current_script_buf.append(data)


SAMPLE_DOCUMENTS = {
    "1": {
        "name": "Production-Grade E-Commerce Product Page (Fully Optimized)",
        "html": """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mechanical Keyboard RGB Hot-Swap - TechMart Indonesia</title>
    <meta name="description" content="Beli Keyboard Mekanikal Switch Hot-Swap dengan backlight RGB per-key kustom. Garansi resmi 2 tahun. Pengiriman instan se-Indonesia.">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <link rel="canonical" href="https://techmart.id/products/mech-keyboard-rgb">
    <link rel="alternate" hreflang="id" href="https://techmart.id/products/mech-keyboard-rgb">
    <link rel="alternate" hreflang="en" href="https://techmart.id/en/products/mech-keyboard-rgb">
    <link rel="alternate" hreflang="x-default" href="https://techmart.id/products/mech-keyboard-rgb">

    <!-- Open Graph (Facebook, WhatsApp, LinkedIn, Discord) -->
    <meta property="og:site_name" content="TechMart Indonesia">
    <meta property="og:type" content="product">
    <meta property="og:title" content="Mechanical Keyboard RGB Hot-Swap - TechMart">
    <meta property="og:description" content="Keyboard mekanikal switch premium untuk programmer dan gamer dengan tata letak ringkas 75%.">
    <meta property="og:url" content="https://techmart.id/products/mech-keyboard-rgb">
    <meta property="og:image" content="https://techmart.id/assets/og-keyboard-1200x630.jpg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:locale" content="id_ID">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@TechMartID">
    <meta name="twitter:creator" content="@TechMartID">
    <meta name="twitter:title" content="Mechanical Keyboard RGB Hot-Swap">
    <meta name="twitter:description" content="Switch kustom, casing alumunium anodized, peredam suara multi-layer.">
    <meta name="twitter:image" content="https://techmart.id/assets/twitter-keyboard.jpg">

    <!-- Structured Data: JSON-LD Schema.org -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org/",
      "@type": "Product",
      "name": "Mechanical Keyboard RGB Hot-Swap",
      "image": [
        "https://techmart.id/assets/keyboard-front.jpg"
      ],
      "description": "Keyboard mekanikal 75% hot-swap dengan switch pra-lubricated.",
      "sku": "TM-KB-RGB-75",
      "brand": {
        "@type": "Brand",
        "name": "TechMart Labs"
      },
      "offers": {
        "@type": "Offer",
        "url": "https://techmart.id/products/mech-keyboard-rgb",
        "priceCurrency": "IDR",
        "price": "1450000",
        "availability": "https://schema.org/InStock",
        "itemCondition": "https://schema.org/NewCondition"
      }
    }
    </script>
</head>
<body>
    <h1>Mechanical Keyboard RGB Hot-Swap</h1>
    <p>Spesifikasi produk lengkap...</p>
</body>
</html>"""
    },
    "2": {
        "name": "Defective Page with Broken SEO & Security Conflicts (Buggy)",
        "html": """<!DOCTYPE html>
<html>
<head>
    <title>Halaman Tanpa Deskripsi</title>
    <!-- Viewport tidak ada! (Gagal Mobile-Friendly) -->
    <!-- Tidak ada meta charset! -->
    <meta name="robots" content="noindex, follow">
    <link rel="canonical" href="http://insecure-domain.com/halaman.html">
    <meta property="og:title" content="Website Rusak">
    <!-- Gambar Open Graph tanpa rasio standar & protokol HTTP tidak aman -->
    <meta property="og:image" content="http://insecure-domain.com/small-icon.png">
    <meta name="twitter:card" content="unknown_card_type">

    <!-- JSON-LD Sintaks Rusak (Trailing comma / Format Invalid) -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "Judul Artikel Bermasalah",
      "missing_required_fields": true,
    }
    </script>
</head>
<body>
    <p>Konten bermasalah dengan audit SEO teknis.</p>
</body>
</html>"""
    }
}


class SEOTechnicalAuditor:
    """Mesin audit teknis SEO, interoperabilitas metadata sosial, dan schema semantic."""

    def __init__(self, raw_html: str):
        self.raw_html = raw_html
        self.parser = MetadataExtractor()
        self.parser.feed(raw_html)
        self.issues: List[Dict[str, Any]] = []
        self.score: int = 100

    def add_issue(self, severity: str, category: str, message: str, penalty: int):
        self.issues.append({
            "severity": severity,
            "category": category,
            "message": message,
            "penalty": penalty
        })
        self.score = max(0, self.score - penalty)

    def audit_head_basics(self):
        # 1. Document Title
        title = (self.parser.title or "").strip()
        if not title:
            self.add_issue("CRITICAL", "Title Tag", "Elemen <title> tidak ditemukan atau kosong.", 20)
        else:
            if len(title) < 20 or len(title) > 65:
                self.add_issue("WARNING", "Title Tag", f"Panjang title ({len(title)} karakter) kurang optimal. Rekomendasi: 30-60 karakter.", 5)

        # 2. Viewport
        viewport_found = any(m.get("name") == "viewport" for m in self.parser.meta_tags)
        if not viewport_found:
            self.add_issue("CRITICAL", "Mobile Readiness", "Meta viewport tidak ditemukan. Berdampak buruk pada Mobile First Indexing.", 15)

        # 3. Charset
        charset_found = any("charset" in m or m.get("http-equiv") == "content-type" for m in self.parser.meta_tags)
        if not charset_found:
            self.add_issue("WARNING", "Encoding", "Deklarasi meta charset UTF-8 tidak ditemukan di awal <head>.", 5)

        # 4. Meta Description
        descriptions = [m.get("content", "").strip() for m in self.parser.meta_tags if m.get("name") == "description"]
        if not descriptions or not descriptions[0]:
            self.add_issue("CRITICAL", "SERP Snippet", "Meta tag 'description' tidak terpasang.", 15)
        else:
            desc_len = len(descriptions[0])
            if desc_len < 70 or desc_len > 160:
                self.add_issue("WARNING", "SERP Snippet", f"Panjang description ({desc_len} karakter) di luar batas ideal 120-155 karakter.", 5)

    def audit_indexing_and_canonical(self):
        # Robots directives
        robots = [m.get("content", "").lower() for m in self.parser.meta_tags if m.get("name") == "robots"]
        if robots:
            combined = ", ".join(robots)
            if "noindex" in combined:
                self.add_issue("WARNING", "Robots Directive", f"Direktif 'noindex' aktif ({combined}). Halaman diinstruksikan tidak diindeks mesin pencari.", 10)

        # Canonical
        canonicals = [link.get("href", "") for link in self.parser.link_tags if link.get("rel") == "canonical"]
        if not canonicals:
            self.add_issue("WARNING", "Canonicalization", "Elemen <link rel='canonical'> tidak disetel untuk mencegah duplikasi konten.", 10)
        elif len(canonicals) > 1:
            self.add_issue("CRITICAL", "Canonicalization", "Ditemukan multiple canonical links! Search crawler akan mengabaikan rel=canonical.", 15)
        else:
            canonical_url = canonicals[0]
            if canonical_url.startswith("http://"):
                self.add_issue("WARNING", "Security / URL", f"Canonical URL menggunakan protokol HTTP tidak aman: {canonical_url}", 5)

        # Alternates / Hreflang
        hreflangs = [link for link in self.parser.link_tags if link.get("rel") == "alternate" and "hreflang" in link]
        if hreflangs:
            has_x_default = any(link.get("hreflang") == "x-default" for link in hreflangs)
            if not has_x_default:
                self.add_issue("INFO", "Internationalization", "hreflang terpasang namun tanpa fallback 'x-default'.", 2)

    def audit_open_graph(self):
        og_props = {}
        for m in self.parser.meta_tags:
            prop = m.get("property", "")
            if prop.startswith("og:"):
                og_props[prop] = m.get("content", "")

        essential_og = ["og:title", "og:type", "og:image", "og:url"]
        for prop in essential_og:
            if prop not in og_props or not og_props[prop]:
                self.add_issue("HIGH", "Open Graph", f"Properti esensial {prop} tidak ditemukan untuk rich card share.", 7)

        if "og:image" in og_props:
            img_url = og_props["og:image"]
            if img_url.startswith("http://"):
                self.add_issue("WARNING", "Open Graph Security", f"og:image menggunakan HTTP biasa. Platform sosial memblokir mixed content: {img_url}", 3)

    def audit_twitter_card(self):
        twitter_meta = {m.get("name", ""): m.get("content", "") for m in self.parser.meta_tags if m.get("name", "").startswith("twitter:")}

        if not twitter_meta:
            self.add_issue("INFO", "Twitter Cards", "Tidak ada meta Twitter Cards (akan otomatis fallback ke Open Graph).", 1)
        else:
            card_type = twitter_meta.get("twitter:card")
            valid_types = ["summary", "summary_large_image", "app", "player"]
            if card_type not in valid_types:
                self.add_issue("HIGH", "Twitter Cards", f"Tipe card '{card_type}' tidak valid. Gunakan salah satu dari: {', '.join(valid_types)}", 5)

    def audit_json_ld(self):
        if not self.parser.json_ld_scripts:
            self.add_issue("INFO", "Structured Data", "Tidak ada schema JSON-LD Schema.org terdeteksi. Rich snippet di SERP tidak aktif.", 5)
            return

        for idx, raw_json in enumerate(self.parser.json_ld_scripts, 1):
            try:
                data = json.loads(raw_json)
                schema_context = data.get("@context", "")
                schema_type = data.get("@type", "")

                if "schema.org" not in schema_context:
                    self.add_issue("HIGH", "Schema.org", f"Script JSON-LD #{idx} tidak menyertakan @context schema.org yang valid.", 5)
                if not schema_type:
                    self.add_issue("HIGH", "Schema.org", f"Script JSON-LD #{idx} kehilangan deklarasi @type.", 5)

            except json.JSONDecodeError as err:
                self.add_issue("CRITICAL", "JSON-LD Syntax", f"Syntax error pada JSON-LD #{idx}: {err}", 15)

    def run_all(self):
        self.audit_head_basics()
        self.audit_indexing_and_canonical()
        self.audit_open_graph()
        self.audit_twitter_card()
        self.audit_json_ld()


def print_banner():
    banner = f"""{COLOR_CYAN}{COLOR_BOLD}
========================================================================
   INTEROPERABILITAS PLATFORM, METADATA & AUDITOR TEKNIS SEO (HTML5)
   Pusat Simulasi Standar Open Graph, Twitter Cards, Canonical & JSON-LD
========================================================================{COLOR_RESET}"""
    print(banner)


def render_social_preview(auditor: MetadataExtractor):
    """Menampilkan simulasi tampilan Card Media Sosial di Terminal."""
    title = auditor.title or "(No Title Specified)"
    desc = next((m.get("content") for m in auditor.meta_tags if m.get("name") == "description"), "No description available.")
    og_title = next((m.get("content") for m in auditor.meta_tags if m.get("property") == "og:title"), title)
    og_image = next((m.get("content") for m in auditor.meta_tags if m.get("property") == "og:image"), "https://via.placeholder.com/1200x630")
    og_site = next((m.get("content") for m in auditor.meta_tags if m.get("property") == "og:site_name"), "DOMAIN.COM")

    print(f"\n{COLOR_MAGENTA}{COLOR_BOLD}[PREVIEW TAMPILAN KARTU SOSIAL: WHATSAPP / LINKEDIN / FACEBOOK]{COLOR_RESET}")
    print(f"{COLOR_GRAY}+-------------------------------------------------------------------+{COLOR_RESET}")
    print(f"{COLOR_GRAY}|{COLOR_RESET} {COLOR_CYAN}[BANNER GAMBAR]{COLOR_RESET} {og_image[:50]}... {COLOR_GRAY}|{COLOR_RESET}")
    print(f"{COLOR_GRAY}|{COLOR_RESET}                                                                   {COLOR_GRAY}|{COLOR_RESET}")
    print(f"{COLOR_GRAY}|{COLOR_RESET} {COLOR_YELLOW}{og_site.upper()}{COLOR_RESET}")
    print(f"{COLOR_GRAY}|{COLOR_RESET} {COLOR_BOLD}{og_title[:63]:<63}{COLOR_RESET} {COLOR_GRAY}|{COLOR_RESET}")
    print(f"{COLOR_GRAY}|{COLOR_RESET} {desc[:63]:<63} {COLOR_GRAY}|{COLOR_RESET}")
    print(f"{COLOR_GRAY}+-------------------------------------------------------------------+{COLOR_RESET}\n")


def display_audit_results(auditor: SEOTechnicalAuditor):
    score = auditor.score
    if score >= 90:
        score_color = COLOR_GREEN
        rating = "EXCELLENT (Production Ready)"
    elif score >= 70:
        score_color = COLOR_YELLOW
        rating = "ACCEPTABLE (Need Improvements)"
    else:
        score_color = COLOR_RED
        rating = "POOR (SEO & Interop At Risk)"

    print(f"{COLOR_BOLD}Audit Score: {score_color}{score}/100 - {rating}{COLOR_RESET}\n")
    print(f"{COLOR_BOLD}{'SEVERITY':<10} | {'CATEGORY':<22} | {'PENALTY':<7} | {'DETAIL TEMUAN':<40}{COLOR_RESET}")
    print("-" * 85)

    if not auditor.issues:
        print(f"{COLOR_GREEN}✓ Tidak ditemukan pelanggaran teknis SEO. Dokumen memenuhi seluruh standar.{COLOR_RESET}")
    else:
        for issue in auditor.issues:
            sev = issue["severity"]
            if sev == "CRITICAL":
                c = COLOR_RED
            elif sev in ("HIGH", "WARNING"):
                c = COLOR_YELLOW
            else:
                c = COLOR_CYAN

            print(f"{c}{sev:<10}{COLOR_RESET} | {issue['category']:<22} | -{issue['penalty']:<6} | {issue['message']}")

    print("-" * 85)


def interactive_menu():
    print_banner()

    while True:
        print(f"\n{COLOR_BOLD}Pilih Skenario Audit atau Masukkan Dokumen HTML Sendiri:{COLOR_RESET}")
        print(f" {COLOR_CYAN}1.{COLOR_RESET} Jalankan Audit Skenario 1: Halaman E-Commerce Optimal (Best Practice)")
        print(f" {COLOR_CYAN}2.{COLOR_RESET} Jalankan Audit Skenario 2: Halaman Bermasalah (Deteksi Error & Warning)")
        print(f" {COLOR_CYAN}3.{COLOR_RESET} Input Snippet HTML Kustom Mandiri")
        print(f" {COLOR_CYAN}4.{COLOR_RESET} Tampilkan Penjelasan Konsep Inti Interoperabilitas Platform & SEO")
        print(f" {COLOR_RED}0. Keluar dari Lab{COLOR_RESET}")

        choice = input(f"\n{COLOR_BOLD}Masukkan pilihan (0-4): {COLOR_RESET}").strip()

        if choice == "0":
            print(f"\n{COLOR_GREEN}Selesai. Lab Interoperabilitas SEO ditutup.{COLOR_RESET}")
            sys.exit(0)

        elif choice in ("1", "2"):
            data = SAMPLE_DOCUMENTS[choice]
            print(f"\n{COLOR_BLUE}>>> Memproses Skenario: {data['name']}...{COLOR_RESET}")
            auditor = SEOTechnicalAuditor(data["html"])
            auditor.run_all()
            render_social_preview(auditor.parser)
            display_audit_results(auditor)

        elif choice == "3":
            print(f"\n{COLOR_YELLOW}Tempelkan markup HTML <head> Anda. Ketik 'SELESAI' di baris baru untuk mulai audit:{COLOR_RESET}")
            lines = []
            while True:
                try:
                    line = input()
                    if line.strip() == "SELESAI":
                        break
                    lines.append(line)
                except EOFError:
                    break
            custom_html = "\n".join(lines)
            if not custom_html.strip():
                print(f"{COLOR_RED}Markup kosong! Dibatalkan.{COLOR_RESET}")
                continue

            auditor = SEOTechnicalAuditor(custom_html)
            auditor.run_all()
            render_social_preview(auditor.parser)
            display_audit_results(auditor)

        elif choice == "4":
            print(f"\n{COLOR_MAGENTA}{COLOR_BOLD}=== KONSEP DASAR INTEROPERABILITAS METADATA & SEO TEKNIS ==={COLOR_RESET}")
            print(f"""
{COLOR_BOLD}1. The Social Graph (Open Graph & Twitter Cards):{COLOR_RESET}
   - HTML bukan lagi sekadar dokumen pembaca lokal browser.
   - Platform pihak ketiga (Slack, Telegram, WhatsApp, Twitter, iMessage) mengikis (scrape)
     metadata meta property='og:*' untuk merender visual interactive rich-card.
   - Rasio gambar standar OG: 1200x630 pixel (1.91:1) dengan fallback minimal 600x315.

{COLOR_BOLD}2. Canonicalization (<link rel='canonical'>):{COLOR_RESET}
   - Menghindari penalti 'Duplicate Content' ketika halaman yang sama bisa diakses
     lewat parameter kueri URL tracking (?utm_source=fb), varian HTTP/HTTPS, atau variasi trailing slash.
   - Menentukan satu URL otoritatif utama untuk akumulasi authority (link equity).

{COLOR_BOLD}3. Semantic Web & Linked Data (JSON-LD Schema.org):{COLOR_RESET}
   - Format standar berbasis JSON yang diinjeksi ke dalam script type='application/ld+json'.
   - Menyediakan taksonomi eksplisit kepada AI agent dan crawler pencari mengenai entitas:
     Product, Article, Organization, BreadcrumbList, FAQPage, atau Event.

{COLOR_BOLD}4. Directives Robots & Crawler Budgeting:{COLOR_RESET}
   - Tag <meta name='robots' content='...'> mengendalikan perizinan crawling dan rendering indexer.
   - Penggunaan 'max-snippet', 'max-image-preview:large', dan 'noindex/nofollow' secara terukur.
""")
        else:
            print(f"{COLOR_RED}Pilihan tidak valid. Silakan coba lagi.{COLOR_RESET}")


if __name__ == "__main__":
    interactive_menu()
