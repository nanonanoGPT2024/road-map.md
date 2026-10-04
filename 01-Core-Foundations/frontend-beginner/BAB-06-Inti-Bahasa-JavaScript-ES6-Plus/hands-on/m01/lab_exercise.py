#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB-06 Inti Bahasa JavaScript (ES6+) Simulator
Fokus Pembelajaran:
 1. Scoping & Hoisting (var vs let/const, Temporal Dead Zone)
 2. Arrow Functions & Lexical Scope vs Dynamic 'this'
 3. Destructuring & Rest/Spread Operator
 4. JS Runtime Simulation: Call Stack, Microtask (Promises), Macrotask (setTimeout)
 5. ES6 Classes & Prototypal Inheritance Simulator
 6. Mini Interactive Quiz ES6+
"""

import sys
import time
import collections

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

def print_header(title):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{MAGENTA}  🚀 {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")

def demo_scoping_hoisting():
    print_header("Modul 1: Scoping, Hoisting, & Temporal Dead Zone (TDZ)")
    print(f"{YELLOW}Simulasi JS Engine dalam membaca deklarasi variabel:{RESET}\n")
    
    code_sample = """
    // JavaScript Code Sample:
    console.log(namaVar); // Output: undefined (Hoisted, diinisialisasi undefined)
    var namaVar = "Kukuh";

    // console.log(namaLet); // ReferenceError: Cannot access 'namaLet' before initialization (TDZ)
    let namaLet = "JavaScript ES6+";
    """
    print(f"{BLUE}{code_sample}{RESET}")

    memory_phase = {
        "var_phase_creation": "namaVar dialokasikan di memory dengan nilai awal 'undefined'",
        "let_phase_creation": "namaLet dialokasikan di memory TETAPI masuk status Uninitialized (TDZ)",
        "var_phase_execution": "Saat baris 3 dieksekusi, nilai diubah menjadi 'Kukuh'",
        "let_phase_execution": "TDZ berakhir di baris 6 saat deklarasi 'let namaLet' dievaluasi"
    }

    for phase, explanation in memory_phase.items():
        print(f"  {GREEN}▶ [{phase}]{RESET}: {explanation}")
        time.sleep(0.1)

    print(f"\n{BOLD}{GREEN}✔ Kesimpulan Scoping:{RESET} Gunakan {BOLD}const{RESET} secara default, {BOLD}let{RESET} saat reassignment diperlukan, dan tinggalkan {BOLD}var{RESET}.")

def demo_arrow_functions():
    print_header("Modul 2: Arrow Functions & Lexical 'this'")
    print(f"{YELLOW}Perbedaan Regular Function vs Arrow Function:{RESET}\n")
    
    comparison = [
        ("Karakteristik", "Regular Function (function)", "Arrow Function (() => {})"),
        ("this Binding", "Dynamic (bergantung siapa pemanggil)", "Lexical (mewarisi enclosing scope)"),
        ("arguments obj", "Tersedia secara implisit", "Tidak ada (gunakan ...args rest param)"),
        ("new (Constructor)", "Bisa dipanggil dengan 'new'", "TypeError: bukan constructor"),
        ("Prototype", "Memiliki properti prototype", "Tidak memiliki prototype")
    ]
    
    for row in comparison:
        print(f"  {CYAN}{row[0]:<18}{RESET} | {YELLOW}{row[1]:<36}{RESET} | {GREEN}{row[2]}{RESET}")

    print(f"\n{BOLD}Contoh Transformasi ES6 Currying & Inline Return:{RESET}")
    print(f"  {BLUE}const hitungPajak = rate => amount => amount + (amount * rate);{RESET}")
    print(f"  {GREEN}hitungPajak(0.11)(100000){RESET} -> {BOLD}111000{RESET}")

def demo_destructuring_rest_spread():
    print_header("Modul 3: Destructuring, Rest, & Spread Operator")
    
    state = {
        "user": {"id": 101, "username": "dev_hero", "role": "admin"},
        "tags": ["frontend", "javascript", "es6"],
        "metadata": {"login_count": 42}
    }
    
    print(f"{YELLOW}State Asli:{RESET} {state}\n")
    print(f"{BOLD}1. Object Destructuring dengan Aliasing & Default Values:{RESET}")
    username = state["user"]["username"]
    role = state["user"].get("role", "guest")
    avatar = state["user"].get("avatar", "default-avatar.png")
    print(f"   const {{ username: uName, role, avatar = 'default-avatar.png' }} = state.user;")
    print(f"   -> uName: {CYAN}{username}{RESET}, role: {CYAN}{role}{RESET}, avatar: {CYAN}{avatar}{RESET}")

    print(f"\n{BOLD}2. Spread Operator untuk Immutable State Update:{RESET}")
    new_state = {
        **state,
        "user": {**state["user"], "role": "superadmin"},
        "tags": [*state["tags"], "react"]
    }
    print(f"   new_state['user']['role']: {GREEN}{new_state['user']['role']}{RESET}")
    print(f"   new_state['tags']: {GREEN}{new_state['tags']}{RESET}")
    print(f"   Apakah state asli berubah? {RED}{state['user']['role'] == new_state['user']['role']}{RESET} (Immutable!)")

def demo_event_loop_simulation():
    print_header("Modul 4: Event Loop, Microtask Queue vs Macrotask Queue")
    print(f"{YELLOW}Simulasi eksekusi kode asinkronus JavaScript:{RESET}\n")

    code_snippet = """
    console.log("1: Synchronous Start");
    setTimeout(() => console.log("2: Macrotask (setTimeout)"), 0);
    Promise.resolve().then(() => console.log("3: Microtask 1 (Promise)"));
    queueMicrotask(() => console.log("4: Microtask 2 (queueMicrotask)"));
    console.log("5: Synchronous End");
    """
    print(f"{BLUE}{code_snippet}{RESET}")

    call_stack = []
    microtasks = collections.deque(["3: Microtask 1 (Promise)", "4: Microtask 2 (queueMicrotask)"])
    macrotasks = collections.deque(["2: Macrotask (setTimeout)"])
    output_log = []

    print(f"{BOLD}Urutan Eksekusi oleh V8 / JS Engine:{RESET}")
    
    # Step 1: Sync calls
    output_log.append("1: Synchronous Start")
    print(f"  {CYAN}[Call Stack Sync]{RESET}   -> '1: Synchronous Start'")
    output_log.append("5: Synchronous End")
    print(f"  {CYAN}[Call Stack Sync]{RESET}   -> '5: Synchronous End'")
    
    # Step 2: Flush microtasks
    print(f"\n  {MAGENTA}[Event Loop Tick]{RESET}   -> Call Stack kosong. Menguras Microtask Queue lebih dahulu:")
    while microtasks:
        item = microtasks.popleft()
        output_log.append(item)
        print(f"    {GREEN}▶ [Microtask Queue]{RESET} {item}")
        time.sleep(0.08)

    # Step 3: Run 1 macrotask
    print(f"\n  {MAGENTA}[Event Loop Tick]{RESET}   -> Microtask kosong. Mengambil 1 task dari Macrotask Queue:")
    while macrotasks:
        item = macrotasks.popleft()
        output_log.append(item)
        print(f"    {YELLOW}▶ [Macrotask Queue]{RESET} {item}")
        time.sleep(0.08)

    print(f"\n{BOLD}{GREEN}Urutan Output Akhir di Console Browser:{RESET}")
    for idx, log in enumerate(output_log, start=1):
        print(f"  {idx}. {log}")

def demo_classes_prototype():
    print_header("Modul 5: ES6 Classes & Syntactic Sugar di atas Prototype")
    
    class ModelJSSimulator:
        def __init__(self, name):
            self.name = name
            
        def prototype_method(self):
            return f"Model prototype method dari {self.name}"

    js_class_code = """
    class Component {
      #privateField = 42; // ES2022 Private Field
      constructor(name) {
        this.name = name;
      }
      render() {
        return `<div>${this.name} (${this.#privateField})</div>`;
      }
    }
    """
    print(f"{BLUE}{js_class_code}{RESET}")
    print(f"  {CYAN}Fakta Engine:{RESET} `class` di JavaScript BUKAN class OOP berbasis compiler tradisional,")
    print(f"  melainkan {BOLD}Syntactic Sugar{RESET} di atas Prototypal Inheritance (`Component.prototype`).")

def run_interactive_quiz():
    print_header("Modul 6: Interactive ES6+ Self-Assessment Quiz")
    
    questions = [
        {
            "q": "Apakah 'let' dan 'const' mengalami hoisting di JavaScript?",
            "opts": [
                "A. Tidak pernah sama sekali",
                "B. Ya, tetapi berada dalam Temporal Dead Zone (TDZ) sampai baris inisialisasi",
                "C. Hanya di lingkungan Node.js, tidak di browser"
            ],
            "ans": "B",
            "explain": "let/const tetap di-hoist saat Creation Phase, namun tidak diinisialisasi nilai default sehingga akses sebelum deklarasi memicu ReferenceError (TDZ)."
        },
        {
            "q": "Di antara Microtask Queue dan Macrotask Queue, mana yang diprioritaskan terlebih dahulu oleh Event Loop setelah Call Stack kosong?",
            "opts": [
                "A. Macrotask Queue (setTimeout/setInterval)",
                "B. Microtask Queue (Promise.then, MutationObserver, queueMicrotask)",
                "C. Keduanya dieksekusi bersamaan secara parallel multithreading"
            ],
            "ans": "B",
            "explain": "Microtask queue selalu dikuras habis hingga kosong sebelum Event Loop mengambil macrotask berikutnya."
        },
        {
            "q": "Apa nilai output dari: console.log(typeof NaN)?",
            "opts": [
                "A. 'undefined'",
                "B. 'nan'",
                "C. 'number'"
            ],
            "ans": "C",
            "explain": "NaN adalah nilai numerik khusus yang merepresentasikan 'Not-a-Number', namun tipenya secara spesifikasi ECMAScript adalah 'number'."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, start=1):
        print(f"{BOLD}Pertanyaan {idx}:{RESET} {item['q']}")
        for opt in item['opts']:
            print(f"  {opt}")
        
        user_choice = input(f"\n{CYAN}Jawaban Anda (A/B/C) atau tekan Enter untuk skip:{RESET} ").strip().upper()
        if user_choice == item['ans']:
            print(f"{GREEN}{BOLD}✓ BENAR!{RESET} {item['explain']}\n")
            score += 1
        elif user_choice in ["A", "B", "C"]:
            print(f"{RED}{BOLD}✗ SALAH.{RESET} Jawaban yang benar adalah {BOLD}{item['ans']}{RESET}. {item['explain']}\n")
        else:
            print(f"{YELLOW}Dilewati.{RESET} Jawaban: {item['ans']}. {item['explain']}\n")

    print(f"{BOLD}{MAGENTA}Hasil Kuis:{RESET} {score}/{len(questions)} soal berhasil dijawab dengan benar.\n")

def main_menu():
    while True:
        print_header("Simulasi Lab Inti JavaScript (ES6+) - Terminal Interactive")
        print(f"  {BOLD}1.{RESET} Demo Scoping, Hoisting & TDZ")
        print(f"  {BOLD}2.{RESET} Demo Arrow Functions & Lexical Scope")
        print(f"  {BOLD}3.{RESET} Demo Destructuring & Rest/Spread Syntax")
        print(f"  {BOLD}4.{RESET} Simulasi Event Loop (Callstack, Microtask, Macrotask)")
        print(f"  {BOLD}5.{RESET} ES6 Classes & Prototypal Inheritance")
        print(f"  {BOLD}6.{RESET} Jalankan Interactive Quiz Mandiri")
        print(f"  {BOLD}7.{RESET} Jalankan Seluruh Demonstrasi (Automated Walkthrough)")
        print(f"  {BOLD}0.{RESET} Keluar")
        
        choice = input(f"\n{CYAN}Pilih menu (0-7):{RESET} ").strip()
        if choice == "1":
            demo_scoping_hoisting()
        elif choice == "2":
            demo_arrow_functions()
        elif choice == "3":
            demo_destructuring_rest_spread()
        elif choice == "4":
            demo_event_loop_simulation()
        elif choice == "5":
            demo_classes_prototype()
        elif choice == "6":
            run_interactive_quiz()
        elif choice == "7":
            demo_scoping_hoisting()
            demo_arrow_functions()
            demo_destructuring_rest_spread()
            demo_event_loop_simulation()
            demo_classes_prototype()
            run_interactive_quiz()
        elif choice == "0":
            print(f"\n{GREEN}Terima kasih telah menjelajahi fondasi JavaScript ES6+! Sampai jumpa.{RESET}\n")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan masukkan angka 0-7.{RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        demo_scoping_hoisting()
        demo_arrow_functions()
        demo_destructuring_rest_spread()
        demo_event_loop_simulation()
        demo_classes_prototype()
    else:
        main_menu()
