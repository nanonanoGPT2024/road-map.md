#!/usr/bin/env python3
"""
Lab Hands-on: Media Responsif, Resource Hints, dan Optimasi Aset
Bab 05 - Modul 02 Deep Dive (HTML Engine Simulation)

Deskripsi:
Script mandiri ini memodelkan cara kerja Browser Engine dalam mengevaluasi
dan mengoptimalkan pemuatan aset HTML tingkat lanjut:
1. Parsing Resource Hints (<link rel="preload|preconnect|dns-prefetch|prefetch">).
2. Algoritma Seleksi Media Responsif (<picture>, <source media/type>, <img> srcset & sizes)
   berdasarkan spesifikasi W3C HTML5 untuk berbagai Device Profiles (Viewport, DPR, Format Support).
3. Simulasi Network Waterfall & Critical Rendering Path (CRP) yang menghitung
   dampak optimasi terhadap LCP (Largest Contentful Paint) dan penghematan bandwidth.
"""

import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple

# --- ANSI Terminal Colors ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BLUE = "\033[94m"
CLR_BG_DARK = "\033[100m"

class HintType(Enum):
    DNS_PREFETCH = "dns-prefetch"
    PRECONNECT = "preconnect"
    PRELOAD = "preload"
    PREFETCH = "prefetch"

class Priority(Enum):
    VERY_HIGH = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

@dataclass
class ResourceHint:
    hint_type: HintType
    href: str
    as_type: Optional[str] = None
    crossorigin: bool = False

@dataclass
class ImageCandidate:
    url: str
    width_descriptor: Optional[int] = None
    density_descriptor: Optional[float] = None
    mime_type: str = "image/jpeg"
    byte_size: int = 0

@dataclass
class SourceRule:
    media_query: Optional[str]
    mime_type: Optional[str]
    candidates: List[ImageCandidate]

@dataclass
class PictureElement:
    id: str
    sources: List[SourceRule]
    fallback_candidate: ImageCandidate
    sizes_attr: str = "100vw"

@dataclass
class DeviceProfile:
    name: str
    viewport_width: int
    viewport_height: int
    dpr: float
    supported_formats: List[str]
    rtt_ms: float
    bandwidth_mbps: float

# --- Mock HTML Documents ---
UNOPTIMIZED_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <title>Toko Online Tradisional</title>
</head>
<body>
    <header>
        <img id="hero-banner" src="https://cdn.example.com/assets/hero-giant-original.jpg" alt="Promo Diskon" />
    </header>
    <main>
        <p>Selamat datang di marketplace kami.</p>
    </main>
</body>
</html>
"""

OPTIMIZED_HTML = """
<!DOCTYPE html>
<html lang="id">
<head>
    <title>Toko Online Modern Teroptimasi</title>
    <!-- Resource Hints -->
    <link rel="dns-prefetch" href="https://analytics.example.com">
    <link rel="preconnect" href="https://cdn.example.com" crossorigin>
    <link rel="preload" href="https://cdn.example.com/assets/hero-desktop-1x.avif" as="image" type="image/avif">
</head>
<body>
    <header>
        <picture id="hero-banner">
            <!-- Format AVIF (High compression) -->
            <source type="image/avif" media="(max-width: 600px)"
                    srcset="https://cdn.example.com/assets/hero-mob-1x.avif 400w,
                            https://cdn.example.com/assets/hero-mob-2x.avif 800w">
            <source type="image/avif" media="(min-width: 601px)"
                    srcset="https://cdn.example.com/assets/hero-desktop-1x.avif 1200w,
                            https://cdn.example.com/assets/hero-desktop-2x.avif 2400w">
            <!-- Format WebP (Fallback modern) -->
            <source type="image/webp" media="(max-width: 600px)"
                    srcset="https://cdn.example.com/assets/hero-mob-1x.webp 400w,
                            https://cdn.example.com/assets/hero-mob-2x.webp 800w">
            <source type="image/webp" media="(min-width: 601px)"
                    srcset="https://cdn.example.com/assets/hero-desktop-1x.webp 1200w,
                            https://cdn.example.com/assets/hero-desktop-2x.webp 2400w">
            <!-- Fallback Standar JPEG -->
            <img src="https://cdn.example.com/assets/hero-fallback.jpg" 
                 sizes="(max-width: 600px) 100vw, 1200px" 
                 alt="Promo Diskon" />
        </picture>
    </header>
    <main>
        <p>Pemuatan aset ultra cepat dengan format modern & hints.</p>
    </main>
</body>
</html>
"""

# Basis data mock ukuran file byte realistik
ASSET_CATALOG = {
    "https://cdn.example.com/assets/hero-giant-original.jpg": 1850 * 1024, # 1.85 MB unoptimized
    "https://cdn.example.com/assets/hero-mob-1x.avif": 24 * 1024,         # 24 KB
    "https://cdn.example.com/assets/hero-mob-2x.avif": 58 * 1024,         # 58 KB
    "https://cdn.example.com/assets/hero-desktop-1x.avif": 85 * 1024,     # 85 KB
    "https://cdn.example.com/assets/hero-desktop-2x.avif": 175 * 1024,    # 175 KB
    "https://cdn.example.com/assets/hero-mob-1x.webp": 38 * 1024,         # 38 KB
    "https://cdn.example.com/assets/hero-mob-2x.webp": 92 * 1024,         # 92 KB
    "https://cdn.example.com/assets/hero-desktop-1x.webp": 130 * 1024,    # 130 KB
    "https://cdn.example.com/assets/hero-desktop-2x.webp": 260 * 1024,    # 260 KB
    "https://cdn.example.com/assets/hero-fallback.jpg": 450 * 1024,       # 450 KB
}

def parse_resource_hints(html: str) -> List[ResourceHint]:
    """
    Mengekstrak tag <link rel="..."> yang bertindak sebagai Resource Hints
    menggunakan Regex parsing deterministik.
    """
    hints = []
    link_pattern = re.compile(r'<link\s+([^>]+)>', re.IGNORECASE)
    attr_pattern = re.compile(r'(\w+)=["\']([^"\']+)["\']')

    for match in link_pattern.finditer(html):
        attrs = dict(attr_pattern.findall(match.group(1)))
        rel = attrs.get('rel', '').lower()
        href = attrs.get('href')
        
        if not href:
            continue

        try:
            hint_enum = HintType(rel)
            hints.append(ResourceHint(
                hint_type=hint_enum,
                href=href,
                as_type=attrs.get('as'),
                crossorigin='crossorigin' in match.group(1).lower()
            ))
        except ValueError:
            # Mengabaikan rel yang bukan resource hint (misal: stylesheet)
            pass
    return hints

def parse_srcset_entries(srcset_str: str, mime_type: str) -> List[ImageCandidate]:
    """
    Mem-parse string srcset standar HTML5 menjadi kandidat gambar
    lengkap dengan width/density descriptor.
    """
    candidates = []
    # Memisahkan entri koma dengan memperhitungkan spasi
    entries = [entry.strip() for entry in srcset_str.split(',') if entry.strip()]
    for entry in entries:
        parts = entry.split()
        if not parts:
            continue
        url = parts[0]
        desc_w = None
        desc_x = None

        if len(parts) > 1:
            descriptor = parts[1]
            if descriptor.endswith('w'):
                desc_w = int(descriptor[:-1])
            elif descriptor.endswith('x'):
                desc_x = float(descriptor[:-1])

        byte_size = ASSET_CATALOG.get(url, 100 * 1024)
        candidates.append(ImageCandidate(
            url=url,
            width_descriptor=desc_w,
            density_descriptor=desc_x,
            mime_type=mime_type,
            byte_size=byte_size
        ))
    return candidates

def parse_picture_elements(html: str) -> List[PictureElement]:
    """
    Mengekstrak elemen <picture> atau fallback <img> independen.
    """
    picture_list = []
    picture_pattern = re.compile(r'<picture\b[^>]*>(.*?)</picture>', re.DOTALL | re.IGNORECASE)
    
    for match in picture_pattern.finditer(html):
        content = match.group(1)
        sources = []

        # Parse source tags
        source_pattern = re.compile(r'<source\s+([^>]+)>', re.IGNORECASE)
        for s_match in source_pattern.finditer(content):
            attrs = dict(re.findall(r'(\w+)=["\']([^"\']+)["\']', s_match.group(1)))
            media = attrs.get('media')
            mime = attrs.get('type')
            srcset = attrs.get('srcset', '')
            candidates = parse_srcset_entries(srcset, mime or 'image/jpeg')
            sources.append(SourceRule(media_query=media, mime_type=mime, candidates=candidates))

        # Fallback img
        img_match = re.search(r'<img\s+([^>]+)>', content, re.IGNORECASE)
        if img_match:
            img_attrs = dict(re.findall(r'(\w+)=["\']([^"\']+)["\']', img_match.group(1)))
            fallback_url = img_attrs.get('src', '')
            sizes = img_attrs.get('sizes', '100vw')
            fallback = ImageCandidate(
                url=fallback_url,
                mime_type='image/jpeg',
                byte_size=ASSET_CATALOG.get(fallback_url, 500 * 1024)
            )
            picture_list.append(PictureElement(
                id="hero-banner",
                sources=sources,
                fallback_candidate=fallback,
                sizes_attr=sizes
            ))

    # Jika tidak ada <picture>, cek untuk raw <img> tag
    if not picture_list:
        raw_img = re.search(r'<img\s+([^>]+)>', html, re.IGNORECASE)
        if raw_img:
            img_attrs = dict(re.findall(r'(\w+)=["\']([^"\']+)["\']', raw_img.group(1)))
            url = img_attrs.get('src', '')
            fallback = ImageCandidate(
                url=url,
                mime_type='image/jpeg',
                byte_size=ASSET_CATALOG.get(url, 1500 * 1024)
            )
            picture_list.append(PictureElement(
                id=img_attrs.get('id', 'raw-img'),
                sources=[],
                fallback_candidate=fallback
            ))
    return picture_list

def evaluate_media_query(mq: Optional[str], viewport_width: int) -> bool:
    """
    Evaluasi sederhana untuk CSS Media Queries dasar: max-width dan min-width.
    """
    if not mq:
        return True
    
    # Regex untuk max-width
    max_w = re.search(r'max-width:\s*(\d+)px', mq)
    if max_w and viewport_width > int(max_w.group(1)):
        return False
        
    # Regex untuk min-width
    min_w = re.search(r'min-width:\s*(\d+)px', mq)
    if min_w and viewport_width < int(min_w.group(1)):
        return False

    return True

def select_best_candidate(candidates: List[ImageCandidate], target_width: int) -> ImageCandidate:
    """
    Mengimplementasikan algoritma browser W3C untuk memilih kandidat srcset:
    Mencari descriptor width terkecil yang masih >= target_width untuk menghindari blur.
    Jika semua kandidat < target_width, pilih yang terbesar yang tersedia.
    """
    if not candidates:
        raise ValueError("Candidates list cannot be empty")
        
    valid_width_candidates = [c for c in candidates if c.width_descriptor is not None]
    if not valid_width_candidates:
        return candidates[0]

    # Urutkan berdasarkan lebar piksel menaik
    sorted_candidates = sorted(valid_width_candidates, key=lambda c: c.width_descriptor)
    
    for candidate in sorted_candidates:
        if candidate.width_descriptor >= target_width:
            return candidate
            
    return sorted_candidates[-1]

def resolve_picture_element(picture: PictureElement, device: DeviceProfile) -> ImageCandidate:
    """
    Logika Rendering Engine Browser:
    1. Cek secara berurutan setiap elemen <source>.
    2. Jika memiliki atribut 'type', pastikan browser mendukung MIME-type tersebut.
    3. Jika memiliki atribut 'media', pastikan viewport lolos evaluasi Media Query.
    4. Ambil kandidat optimal dari srcset sesuai density target = Viewport * DPR.
    5. Fallback ke elemen default <img> jika tidak ada yang cocok.
    """
    target_pixel_density = int(device.viewport_width * device.dpr)

    for source in picture.sources:
        # Validasi dukungan format (AVIF, WebP, dll.)
        if source.mime_type and source.mime_type not in device.supported_formats:
            continue

        # Validasi media queries
        if not evaluate_media_query(source.media_query, device.viewport_width):
            continue

        # Jika cocok, pilih kandidat terbaik
        return select_best_candidate(source.candidates, target_pixel_density)

    return picture.fallback_candidate

def simulate_network_timing(
    asset: ImageCandidate,
    hints: List[ResourceHint],
    device: DeviceProfile
) -> Dict[str, float]:
    """
    Simulasi matematis waterfall jaringan browser:
    - DNS Lookup: 1x RTT (Dihapus jika ada dns-prefetch atau preconnect)
    - TCP Handshake + TLS: 2x RTT (Dihapus jika ada preconnect)
    - TTFB (Time to First Byte): 1x RTT
    - Waktu Transfer Payload: (Ukuran File dalam Bits / Bandwidth bps)
    - Penjadwalan: Preload memajukan inisialisasi request sebanyak 120ms (tidak terhalang antrian parser)
    """
    dns_time = device.rtt_ms
    connect_time = device.rtt_ms * 2.0
    ttfb = device.rtt_ms

    has_preconnect = any(h.hint_type == HintType.PRECONNECT for h in hints)
    has_dns_prefetch = any(h.hint_type == HintType.DNS_PREFETCH for h in hints)
    is_preloaded = any(h.hint_type == HintType.PRELOAD and h.href == asset.url for h in hints)

    # Optimasi resource hints
    if has_preconnect:
        dns_time = 0.0
        connect_time = 0.0
    elif has_dns_prefetch:
        dns_time = 0.0

    bandwidth_bytes_per_sec = (device.bandwidth_mbps * 1_000_000) / 8.0
    transfer_time_sec = asset.byte_size / bandwidth_bytes_per_sec
    transfer_time_ms = transfer_time_sec * 1000.0

    # Delay penemuan aset oleh parser HTML jika tidak di-preload
    parser_discovery_delay_ms = 0.0 if is_preloaded else 150.0

    total_latency_ms = parser_discovery_delay_ms + dns_time + connect_time + ttfb + transfer_time_ms

    return {
        "dns_ms": dns_time,
        "connect_ms": connect_time,
        "ttfb_ms": ttfb,
        "transfer_ms": transfer_time_ms,
        "parser_delay_ms": parser_discovery_delay_ms,
        "lcp_ms": total_latency_ms
    }

def print_separator(title: str = ""):
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== {title.upper()} ==={CLR_RESET}")

def run_simulation():
    print(f"{CLR_BOLD}{CLR_CYAN}LAB: Media Responsif, Resource Hints, dan Optimasi Aset{CLR_RESET}")
    print(f"Engine Emulator: {CLR_GREEN}Blink/WebKit CRP Simulation Engine{CLR_RESET}\n")

    # Siapkan skenario profil perangkat
    devices = [
        DeviceProfile(
            name="Ponsel Menengah (4G Mobile)",
            viewport_width=390,
            viewport_height=844,
            dpr=2.0,
            supported_formats=["image/webp", "image/avif"],
            rtt_ms=45.0,
            bandwidth_mbps=12.0
        ),
        DeviceProfile(
            name="Laptop Desktop Modern (Kabel Fiber)",
            viewport_width=1440,
            viewport_height=900,
            dpr=1.0,
            supported_formats=["image/webp", "image/avif"],
            rtt_ms=10.0,
            bandwidth_mbps=85.0
        ),
        DeviceProfile(
            name="Perangkat Legacy (Koneksi Lemah, No AVIF)",
            viewport_width=360,
            viewport_height=640,
            dpr=1.5,
            supported_formats=["image/webp"], # Tanpa AVIF
            rtt_ms=90.0,
            bandwidth_mbps=4.0
        )
    ]

    for device in devices:
        print_separator(f"Testing Device: {device.name}")
        print(f"Viewport: {CLR_YELLOW}{device.viewport_width}x{device.viewport_height}px @ DPR {device.dpr}x{CLR_RESET} | "
              f"RTT: {CLR_YELLOW}{device.rtt_ms}ms{CLR_RESET} | Bandwidth: {CLR_YELLOW}{device.bandwidth_mbps} Mbps{CLR_RESET}")
        print(f"Format yang didukung: {', '.join(device.supported_formats)}")

        # 1. Evaluasi Unoptimized HTML
        unopt_hints = parse_resource_hints(UNOPTIMIZED_HTML)
        unopt_pictures = parse_picture_elements(UNOPTIMIZED_HTML)
        unopt_chosen = resolve_picture_element(unopt_pictures[0], device)
        unopt_metrics = simulate_network_timing(unopt_chosen, unopt_hints, device)

        # 2. Evaluasi Optimized HTML
        opt_hints = parse_resource_hints(OPTIMIZED_HTML)
        opt_pictures = parse_picture_elements(OPTIMIZED_HTML)
        opt_chosen = resolve_picture_element(opt_pictures[0], device)
        opt_metrics = simulate_network_timing(opt_chosen, opt_hints, device)

        # Format visualisasi tabel perbandingan
        print(f"\n{CLR_BOLD}{'Metric / Parameter':<30} | {'Unoptimized (Traditional)':<28} | {'Optimized (Modern Spec)':<28}{CLR_RESET}")
        print("-" * 92)
        
        asset_str_unopt = unopt_chosen.url.split('/')[-1]
        asset_str_opt = opt_chosen.url.split('/')[-1]
        print(f"{'Selected Asset':<30} | {asset_str_unopt:<28} | {CLR_GREEN}{asset_str_opt:<28}{CLR_RESET}")

        mime_str_unopt = unopt_chosen.mime_type
        mime_str_opt = opt_chosen.mime_type
        print(f"{'MIME Type':<30} | {mime_str_unopt:<28} | {CLR_GREEN}{mime_str_opt:<28}{CLR_RESET}")

        size_kb_unopt = f"{unopt_chosen.byte_size / 1024:.1f} KB"
        size_kb_opt = f"{opt_chosen.byte_size / 1024:.1f} KB"
        saved_bytes_pct = ((unopt_chosen.byte_size - opt_chosen.byte_size) / unopt_chosen.byte_size) * 100
        print(f"{'Payload Size':<30} | {size_kb_unopt:<28} | {CLR_GREEN}{size_kb_opt} (-{saved_bytes_pct:.1f}%){CLR_RESET}")

        dns_conn_unopt = f"{unopt_metrics['dns_ms'] + unopt_metrics['connect_ms']:.1f} ms"
        dns_conn_opt = f"{opt_metrics['dns_ms'] + opt_metrics['connect_ms']:.1f} ms"
        print(f"{'DNS + Handshake Latency':<30} | {dns_conn_unopt:<28} | {CLR_GREEN}{dns_conn_opt} (Preconnected){CLR_RESET}")

        transfer_unopt = f"{unopt_metrics['transfer_ms']:.1f} ms"
        transfer_opt = f"{opt_metrics['transfer_ms']:.1f} ms"
        print(f"{'Download Transfer Time':<30} | {transfer_unopt:<28} | {CLR_GREEN}{transfer_opt:<28}{CLR_RESET}")

        lcp_unopt = f"{unopt_metrics['lcp_ms']:.1f} ms"
        lcp_opt = f"{opt_metrics['lcp_ms']:.1f} ms"
        speedup = unopt_metrics['lcp_ms'] / opt_metrics['lcp_ms']
        print(f"{CLR_BOLD}{'Est. LCP (Time to Render)':<30} | {CLR_RED}{lcp_unopt:<28}{CLR_RESET} | {CLR_BOLD}{CLR_GREEN}{lcp_opt} ({speedup:.1f}x Faster){CLR_RESET}")

    # Ringkasan Eksekutif Algoritma
    print_separator("Analisis Arsitektural Resource Hints & Media Queries")
    print(f"1. {CLR_BOLD}preconnect & dns-prefetch:{CLR_RESET} Menghilangkan 3 network round-trips (RTT) pada jalur kritis.")
    print(f"2. {CLR_BOLD}preload as='image':{CLR_RESET} Mengabaikan delay antrean scanner parser, menginstruksikan fetcher segera.")
    print(f"3. {CLR_BOLD}<picture> & srcset:{CLR_RESET} Mengirimkan piksel tepat sasaran sesuai DPR dan format terkompresi.")
    print(f"Status Simulasi: {CLR_GREEN}Semua skenario pengujian berhasil dievaluasi tanpa error.{CLR_RESET}\n")

if __name__ == "__main__":
    run_simulation()