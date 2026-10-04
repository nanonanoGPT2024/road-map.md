#!/usr/bin/env python3
"""
Simulasi Information Architecture & Tree Testing Evaluator

Script ini mensimulasikan bagaimana pengguna melakukan navigasi melalui struktur 
Arsitektur Informasi (IA) yang didefinisikan menggunakan format pohon (tree/dictionary).
Tujuannya adalah mengukur "Findability" dan "Path Efficiency" 
(membandingkan langkah aktual pengguna simulasi vs langkah ideal/terpendek).
"""

import os
import sys
import time
import json
import collections

# Clear screen utility
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# ANSI Colors for terminal visualization
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Struktur IA (Information Architecture) - E-commerce Sederhana
ia_tree = {
    "Home": {
        "Elektronik": {
            "Smartphone": ["Apple", "Samsung", "Xiaomi"],
            "Laptop": ["MacBook", "Asus", "Lenovo"],
            "Aksesoris": ["Kabel", "Charger", "Headset"]
        },
        "Pakaian": {
            "Pria": ["Kemeja", "Celana", "Sepatu Pria"],
            "Wanita": ["Gaun", "Rok", "Sepatu Wanita"]
        },
        "Kebutuhan Rumah": {
            "Dapur": ["Panci", "Pisau", "Blender"],
            "Kamar": ["Sprei", "Bantal", "Lemari"]
        },
        "Bantuan": ["FAQ", "Hubungi Kami", "Pengembalian Dana"]
    }
}

def print_tree(tree, indent=""):
    """Fungsi rekursif untuk mencetak struktur pohon IA"""
    if isinstance(tree, dict):
        for i, (key, value) in enumerate(tree.items()):
            is_last = (i == len(tree) - 1)
            prefix = "└── " if is_last else "├── "
            print(f"{indent}{Colors.OKBLUE}{prefix}{key}{Colors.ENDC}")
            next_indent = indent + ("    " if is_last else "│   ")
            print_tree(value, next_indent)
    elif isinstance(tree, list):
        for i, item in enumerate(tree):
            is_last = (i == len(tree) - 1)
            prefix = "└── " if is_last else "├── "
            print(f"{indent}{Colors.OKGREEN}{prefix}{item}{Colors.ENDC}")
    else:
        print(f"{indent}{Colors.OKGREEN}└── {tree}{Colors.ENDC}")

def find_path(tree, target, path=None):
    """Mencari jalur ideal/terpendek menuju target dalam IA tree"""
    if path is None:
        path = []
        
    if isinstance(tree, dict):
        for key, value in tree.items():
            if key.lower() == target.lower():
                return path + [key]
            
            result = find_path(value, target, path + [key])
            if result: return result
            
    elif isinstance(tree, list):
        for item in tree:
            if str(item).lower() == target.lower():
                return path + [item]
                
    return None

def simulate_tree_testing():
    """Simulasi pengujian IA (Tree Testing) interaktif"""
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}=== SIMULASI TREE TESTING & INFORMATION ARCHITECTURE ==={Colors.ENDC}")
    print("Menganalisis Arsitektur Informasi (IA) saat ini...\n")
    time.sleep(1)
    
    print(f"{Colors.BOLD}Struktur IA (Sitemap):{Colors.ENDC}")
    print_tree(ia_tree)
    print("\n")
    
    tasks = ["Blender", "Pengembalian Dana", "Headset", "Kemeja"]
    
    print(f"{Colors.WARNING}Memulai Uji 'Findability' (Tingkat Keterbukaan).{Colors.ENDC}")
    print("Simulasi bot pengguna mencari beberapa item dalam hierarki...\n")
    time.sleep(1.5)
    
    total_score = 0
    for task in tasks:
        print(f"{Colors.BOLD}Tugas:{Colors.ENDC} Mencari '{Colors.OKCYAN}{task}{Colors.ENDC}'")
        print("Menghitung rute ideal...")
        time.sleep(0.8)
        
        ideal_path = find_path(ia_tree["Home"], task, ["Home"])
        
        if ideal_path:
            path_str = " > ".join(ideal_path)
            steps = len(ideal_path) - 1
            print(f"{Colors.OKGREEN}✓ Ditemukan!{Colors.ENDC}")
            print(f"  Jalur     : {path_str}")
            print(f"  Kedalaman : {steps} klik (tingkat/level)")
            
            if steps <= 3:
                print(f"  Analisis  : {Colors.OKGREEN}Sangat Baik (IA dangkal dan mudah diakses){Colors.ENDC}")
                total_score += 100
            elif steps == 4:
                print(f"  Analisis  : {Colors.WARNING}Sedang (Mungkin butuh shortcut/pencarian){Colors.ENDC}")
                total_score += 70
            else:
                print(f"  Analisis  : {Colors.FAIL}Buruk (Terlalu dalam, risiko cognitive overload){Colors.ENDC}")
                total_score += 40
        else:
            print(f"{Colors.FAIL}✗ Gagal! Item '{task}' tidak ditemukan dalam IA.{Colors.ENDC}")
            print(f"  Analisis  : {Colors.FAIL}Mental Model mismatch atau item hilang.{Colors.ENDC}")
            
        print("-" * 50)
        time.sleep(1)

    avg_score = total_score / len(tasks)
    print(f"\n{Colors.HEADER}=== HASIL EVALUASI IA ==={Colors.ENDC}")
    print(f"Skor Keseluruhan (Findability Score) : {avg_score:.1f} / 100")
    
    if avg_score >= 80:
        print(f"Status IA : {Colors.OKGREEN}SEHAT{Colors.ENDC}. Arsitektur Informasi sudah selaras dengan pola pencarian yang efisien.")
    elif avg_score >= 60:
        print(f"Status IA : {Colors.WARNING}PERLU PERBAIKAN{Colors.ENDC}. Pertimbangkan menyederhanakan kategori.")
    else:
        print(f"Status IA : {Colors.FAIL}KRITIS{Colors.ENDC}. Perlu restrukturisasi total (Card Sorting ulang dianjurkan).")

if __name__ == "__main__":
    try:
        simulate_tree_testing()
    except KeyboardInterrupt:
        print("\nSimulasi dihentikan.")
        sys.exit(0)
