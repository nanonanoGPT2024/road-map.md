#!/usr/bin/env python3
"""
Micro-Interaction & Motion Simulation in Terminal
Simulasi bagaimana berbagai jenis fungsi Easing dan Feedback State (Success, Error)
mempengaruhi rasa interaksi. Ini merepresentasikan logika yang sama yang 
akan Anda gunakan pada CSS/JS Animations di Frontend.
"""

import sys
import time
import math
import os

# ANSI Colors & Styles
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
CLEAR_LINE = "\033[2K\r"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

# Easing Functions
# x is progress from 0 to 1
def linear(x):
    return x

def ease_out_quad(x):
    return 1 - (1 - x) * (1 - x)

def ease_in_quad(x):
    return x * x

def ease_in_out_quad(x):
    if x < 0.5:
        return 2 * x * x
    return 1 - math.pow(-2 * x + 2, 2) / 2

class InteractionSimulator:
    def __init__(self, fps=60):
        self.fps = fps
        self.frame_duration = 1.0 / fps

    def run_progress_bar(self, duration, easing_func, name):
        sys.stdout.write(f"\n{CYAN}{BOLD}▶ Simulasi Progress Bar - {name}{RESET}\n")
        bar_length = 50
        frames = int(duration * self.fps)
        
        for frame in range(frames + 1):
            progress = frame / frames
            eased_progress = easing_func(progress)
            
            filled_length = int(bar_length * eased_progress)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            
            percent = int(eased_progress * 100)
            sys.stdout.write(f"{CLEAR_LINE}Loading: |{bar}| {percent}% ")
            sys.stdout.flush()
            time.sleep(self.frame_duration)
            
        print()

    def run_spinner_feedback(self, duration):
        sys.stdout.write(f"\n{YELLOW}{BOLD}▶ Simulasi Async Action (Trigger -> Loading -> Success Feedback){RESET}\n")
        spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        frames = int(duration * self.fps)
        
        # State: Loading
        for frame in range(frames):
            idx = (frame // 3) % len(spinner_chars)
            sys.stdout.write(f"{CLEAR_LINE}{CYAN}{spinner_chars[idx]} Memproses tindakan...{RESET}")
            sys.stdout.flush()
            time.sleep(self.frame_duration)
            
        # State: Success
        time.sleep(0.1) # micro-pause
        sys.stdout.write(f"{CLEAR_LINE}{GREEN}✔ Tindakan Berhasil! (Success Feedback){RESET}\n")
        sys.stdout.flush()

    def run_error_shake(self):
        sys.stdout.write(f"\n{RED}{BOLD}▶ Simulasi Error Feedback (Shake Animation){RESET}\n")
        text = "❌ Terjadi Kesalahan: Koneksi Terputus"
        # Shake sequence: offset spaces
        offsets = [0, 4, -4, 3, -3, 2, -2, 1, -1, 0]
        
        for offset in offsets:
            pad_left = max(0, 10 + offset)
            display_text = " " * pad_left + text
            sys.stdout.write(f"{CLEAR_LINE}{RED}{display_text}{RESET}")
            sys.stdout.flush()
            time.sleep(0.08)
        print("\n")

def main():
    os.system("") # Enable ANSI colors in Windows CMD if needed
    sim = InteractionSimulator(fps=60)
    
    try:
        sys.stdout.write(HIDE_CURSOR)
        print(f"{BOLD}=== Micro-Interaction & Motion Lab ==={RESET}")
        print("Mendemonstrasikan perbedaan *feeling* berdasarkan easing dan feedback states.\n")
        
        time.sleep(1)
        
        # 1. Bandingkan Easing
        print(f"{BOLD}[1] Perbandingan Easing (Durasi 2 Detik){RESET}")
        sim.run_progress_bar(2.0, linear, "Linear (Mekanikal, Kurang Natural)")
        sim.run_progress_bar(2.0, ease_out_quad, "Ease Out (Cepat di awal, Melambat di akhir)")
        sim.run_progress_bar(2.0, ease_in_out_quad, "Ease In Out (Transisi mulus di awal & akhir)")
        
        time.sleep(1)
        
        # 2. Loading State
        print(f"\n{BOLD}[2] Micro-interaction Loop & State Change{RESET}")
        sim.run_spinner_feedback(2.5)
        
        time.sleep(1)
        
        # 3. Error State
        print(f"\n{BOLD}[3] Error Handling & Haptic-like Visual Feedback{RESET}")
        sim.run_error_shake()
        
        print(f"{BOLD}Lab Selesai. Perhatikan bagaimana feedback visual mempengaruhi User Experience.{RESET}")
        
    except KeyboardInterrupt:
        print(f"\n{RED}Lab dihentikan.{RESET}")
    finally:
        sys.stdout.write(SHOW_CURSOR)

if __name__ == "__main__":
    main()
