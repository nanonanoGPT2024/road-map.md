#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Linux Network Stack, Syscall Socket, dan TCP/IP State Machine
BAB 06: Jaringan Linux, Socket, dan TCP/IP Stack
"""

import sys
import time
import socket
import threading
from typing import Dict, Any

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_BLUE = "\033[94m"
CLR_BG_DARK = "\033[48;5;236m"

def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}======================================================================
  LAB HANDS-ON: LINUX SOCKET API & TCP/IP PROTOCOL STACK SIMULATOR
  Topik: BAB 06 - Jaringan Linux, Socket, dan TCP/IP Stack
======================================================================{CLR_RESET}
"""
    print(banner)

def step_delay(seconds: float = 0.6):
    time.sleep(seconds)

def simulate_tcp_handshake():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}[SIMULASI 1: TCP 3-Way Handshake & 4-Way Teardown]{CLR_RESET}")
    print(f"{CLR_BLUE}Klien (192.168.1.50:49152) <---> Server (192.168.1.10:80){CLR_RESET}\n")

    steps = [
        ("CLIENT", "SYN (Seq=1000, Ack=0, Flags=[S])", "SYN_SENT", "LISTEN"),
        ("SERVER", "SYN-ACK (Seq=5000, Ack=1001, Flags=[S, .])", "SYN_SENT", "SYN_RECV"),
        ("CLIENT", "ACK (Seq=1001, Ack=5001, Flags=[.])", "ESTABLISHED", "ESTABLISHED"),
    ]

    print(f"{CLR_BOLD}{'Aktor':<8} | {'Paket / Sinyal TCP':<42} | {'State Klien':<13} | {'State Server'}{CLR_RESET}")
    print("-" * 80)

    for actor, packet, c_state, s_state in steps:
        color = CLR_GREEN if actor == "CLIENT" else CLR_CYAN
        print(f"{color}{actor:<8}{CLR_RESET} | {packet:<42} | {c_state:<13} | {s_state}")
        step_delay(0.7)

    print(f"\n{CLR_GREEN}{CLR_BOLD}[+] Koneksi Berhasil Berstatus ESTABLISHED! Saluran data dua arah siap.{CLR_RESET}\n")
    step_delay(0.5)

    print(f"{CLR_YELLOW}Simulasi Pengiriman Data (send / recv):{CLR_RESET}")
    print(f"CLIENT -> [PSH, ACK] Data: 'GET / HTTP/1.1\\r\\n' (Len=16, Seq=1001, Ack=5001)")
    step_delay(0.4)
    print(f"SERVER -> [ACK] Seq=5001, Ack=1017 (Kernel server menerima payload ke RX buffer)")
    step_delay(0.4)
    print(f"SERVER -> [PSH, ACK] Data: 'HTTP/1.1 200 OK\\r\\n' (Len=17, Seq=5001, Ack=1017)")
    step_delay(0.4)
    print(f"CLIENT -> [ACK] Seq=1017, Ack=5018 (Payload masuk ke RX buffer aplikasi klien)")
    step_delay(0.6)

    print(f"\n{CLR_RED}{CLR_BOLD}Terminasi Koneksi (4-Way Handshake):{CLR_RESET}")
    teardown_steps = [
        ("CLIENT", "FIN, ACK (Seq=1017, Ack=5018)", "FIN_WAIT_1", "ESTABLISHED"),
        ("SERVER", "ACK (Seq=5018, Ack=1018)", "FIN_WAIT_2", "CLOSE_WAIT"),
        ("SERVER", "FIN, ACK (Seq=5018, Ack=1018)", "TIME_WAIT", "LAST_ACK"),
        ("CLIENT", "ACK (Seq=1018, Ack=5019)", "TIME_WAIT (60s)", "CLOSED"),
    ]
    for actor, packet, c_state, s_state in teardown_steps:
        color = CLR_RED if actor == "CLIENT" else CLR_YELLOW
        print(f"{color}{actor:<8}{CLR_RESET} | {packet:<42} | {c_state:<15} | {s_state}")
        step_delay(0.6)

    print(f"\n{CLR_CYAN}Catatan Inti Linux Kernel:{CLR_RESET}")
    print("- State TIME_WAIT ditahan selama 2 * MSL (Maximum Segment Lifetime) default 60 detik.")
    print("- Mencegah paket duplikat lama merusak koneksi baru dengan 4-tuple yang identik.")

def simulate_socket_lifecycle():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}[SIMULASI 2: Siklus Hidup Socket API & Linux Kernel Syscalls]{CLR_RESET}\n")

    stages = [
        ("1. socket()", "sys_socket(AF_INET, SOCK_STREAM, 0)", "Alokasi struct socket & VFS struct file (File Descriptor baru, misal FD 3)."),
        ("2. bind()", "sys_bind(fd=3, addr=0.0.0.0:8080)", "Mengasosiasikan socket descriptor dengan IP lokal dan nomor port (sk_node di hash table)."),
        ("3. listen()", "sys_listen(fd=3, backlog=128)", "Mengubah status socket ke LISTEN. Inisialisasi SYN backlog queue dan accept queue."),
        ("4. connect()", "sys_connect(fd=4, addr=127.0.0.1:8080)", "Klien mengalokasikan port ephemeral, mengirim SYN paket, menunggu SYN-ACK."),
        ("5. accept()", "sys_accept4(fd=3, ...)", "Kernel mengambil koneksi matang dari accept queue, menghasilkan FD BARU (misal FD 5)."),
        ("6. send/recv", "sys_write / sys_read (atau send/recv)", "Menyalin buffer antara user space memory dan sk_buff di kernel space."),
        ("7. close()", "sys_close(fd)", "Menutup FD, memicu FIN jika refcount=0, mengalihkan state ke FIN_WAIT/TIME_WAIT.")
    ]

    for stage, syscall, explanation in stages:
        print(f"{CLR_CYAN}{CLR_BOLD}{stage:<16}{CLR_RESET} -> {CLR_YELLOW}{syscall}{CLR_RESET}")
        print(f"   {CLR_GREEN}Kernel Action:{CLR_RESET} {explanation}\n")
        step_delay(0.5)

def run_real_loopback_demo():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}[SIMULASI 3: Eksekusi Nyata Socket TCP Loopback (Client-Server Threaded)]{CLR_RESET}")
    
    server_ready = threading.Event()
    server_port = 0

    def tcp_server():
        nonlocal server_port
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv_sock.bind(("127.0.0.1", 0))
        server_port = srv_sock.getsockname()[1]
        srv_sock.listen(1)
        print(f"  {CLR_GREEN}[SERVER]{CLR_RESET} socket() + bind() ke 127.0.0.1:{server_port} + listen() OK.")
        server_ready.set()

        conn, addr = srv_sock.accept()
        print(f"  {CLR_GREEN}[SERVER]{CLR_RESET} accept() menerima koneksi dari {addr[0]}:{addr[1]}")
        data = conn.recv(1024)
        print(f"  {CLR_GREEN}[SERVER]{CLR_RESET} recv() membaca: {data.decode(errors='replace')}")
        conn.sendall(b"ACK-FROM-KERNEL-LINUX-SERVER")
        print(f"  {CLR_GREEN}[SERVER]{CLR_RESET} sendall() membalas payload, lalu close connection.")
        conn.close()
        srv_sock.close()

    server_thread = threading.Thread(target=tcp_server, daemon=True)
    server_thread.start()
    server_ready.wait()

    # Client run
    print(f"  {CLR_BLUE}[CLIENT]{CLR_RESET} Membuat socket AF_INET, SOCK_STREAM...")
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    step_delay(0.3)
    print(f"  {CLR_BLUE}[CLIENT]{CLR_RESET} Melakukan connect() ke 127.0.0.1:{server_port}...")
    client_sock.connect(("127.0.0.1", server_port))
    client_laddr = client_sock.getsockname()
    print(f"  {CLR_BLUE}[CLIENT]{CLR_RESET} Terhubung! Port ephemeral lokal: {client_laddr[1]}")
    step_delay(0.3)
    msg = b"HELLO LINUX NETWORKING"
    print(f"  {CLR_BLUE}[CLIENT]{CLR_RESET} send() payload: {msg.decode()}")
    client_sock.sendall(msg)
    response = client_sock.recv(1024)
    print(f"  {CLR_BLUE}[CLIENT]{CLR_RESET} recv() respon: {response.decode(errors='replace')}")
    client_sock.close()
    print(f"  {CLR_BLUE}[CLIENT]{CLR_RESET} Socket ditutup.\n")
    server_thread.join()

def display_kernel_buffers():
    print(f"\n{CLR_MAGENTA}{CLR_BOLD}[SIMULASI 4: Inspeksi Struktur Buffer Kernel (sk_buff & Tunables)]{CLR_RESET}\n")
    
    tunables = {
        "/proc/sys/net/ipv4/tcp_max_syn_backlog": "Kapasitas antrean setengah matang (SYN_RECV queue).",
        "/proc/sys/net/core/somaxconn": "Batas maksimum parameter backlog listen() (Accept queue).",
        "/proc/sys/net/ipv4/tcp_wmem": "Min, default, dan max ukuran buffer transmisi TX socket TCP.",
        "/proc/sys/net/ipv4/tcp_rmem": "Min, default, dan max ukuran buffer penerimaan RX socket TCP.",
        "/proc/sys/net/ipv4/tcp_fin_timeout": "Waktu timeout (dalam detik) di state FIN_WAIT_2 sebelum di-drop."
    }

    print(f"{CLR_BOLD}{'Parameter Kernel (Sysctl)':<42} | {'Fungsi & Relevansi Arsitektural'}{CLR_RESET}")
    print("-" * 85)
    for path, desc in tunables.items():
        print(f"{CLR_YELLOW}{path:<42}{CLR_RESET} | {desc}")
    print()

def interactive_menu():
    while True:
        print_banner()
        print(f"{CLR_BOLD}Pilih Modul Simulasi:{CLR_RESET}")
        print(f"  {CLR_CYAN}1.{CLR_RESET} Simulasi TCP 3-Way Handshake & 4-Way Teardown (State Machine)")
        print(f"  {CLR_CYAN}2.{CLR_RESET} Visualisasi Syscall Socket API & Interaksi Kernel")
        print(f"  {CLR_CYAN}3.{CLR_RESET} Live Demo Socket Client-Server (Loopback TCP)")
        print(f"  {CLR_CYAN}4.{CLR_RESET} Inspeksi Tunables TCP Kernel Linux (/proc/sys/net)")
        print(f"  {CLR_CYAN}5.{CLR_RESET} Jalankan Seluruh Simulasi Sekaligus")
        print(f"  {CLR_RED}0.{CLR_RESET} Keluar (Exit)")
        
        try:
            choice = input(f"\n{CLR_BOLD}Masukkan pilihan [0-5]: {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSelesai.")
            break

        if choice == "1":
            simulate_tcp_handshake()
        elif choice == "2":
            simulate_socket_lifecycle()
        elif choice == "3":
            run_real_loopback_demo()
        elif choice == "4":
            display_kernel_buffers()
        elif choice == "5":
            simulate_tcp_handshake()
            simulate_socket_lifecycle()
            run_real_loopback_demo()
            display_kernel_buffers()
        elif choice == "0":
            print(f"\n{CLR_GREEN}Sampai jumpa di eksplorasi kernel networking selanjutnya!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan pilih 0-5.{CLR_RESET}")

        input(f"\n{CLR_CYAN}Tekan [Enter] untuk kembali ke menu utama...{CLR_RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        simulate_tcp_handshake()
        simulate_socket_lifecycle()
        run_real_loopback_demo()
        display_kernel_buffers()
    else:
        interactive_menu()
