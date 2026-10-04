#!/usr/bin/env python3
"""
BAB 10: Komputasi Lanjutan & Tren Masa Depan
Lab Hands-on M01: Simulasi Interaktif Quantum State, Superposisi, dan Entanglement Bell State
Serta Toy-Model Neuromorphic Spiking Neuron (Leaky Integrate-and-Fire).
"""

import sys
import math
import random
import time

# ANSI Escape Colors for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"


def header(title: str):
    print(f"\n{BOLD}{BG_BLUE}  === {title.upper()} ===  {RESET}\n")


def print_status(label: str, val: str, color=CYAN):
    print(f"  {BOLD}{label:<24}:{RESET} {color}{val}{RESET}")


class QuantumState:
    """
    Simulasi State Vector 1-Qubit: |psi> = alpha|0> + beta|1>
    dengan syarat normalisasi: |alpha|^2 + |beta|^2 = 1.
    """
    def __init__(self, alpha: complex = 1.0 + 0j, beta: complex = 0.0 + 0j):
        self.alpha = complex(alpha)
        self.beta = complex(beta)
        self._normalize()

    def _normalize(self):
        norm = math.sqrt(abs(self.alpha)**2 + abs(self.beta)**2)
        if norm > 1e-12:
            self.alpha /= norm
            self.beta /= norm

    def apply_hadamard(self):
        """Hadamard Gate (H): Menciptakan status superposisi sempurna."""
        inv_sqrt2 = 1.0 / math.sqrt(2.0)
        new_alpha = inv_sqrt2 * (self.alpha + self.beta)
        new_beta = inv_sqrt2 * (self.alpha - self.beta)
        self.alpha, self.beta = new_alpha, new_beta
        self._normalize()

    def apply_pauli_x(self):
        """Pauli-X (NOT Gate quantum): membalik amplitudo |0> dan |1>."""
        self.alpha, self.beta = self.beta, self.alpha

    def apply_phase_shift(self, theta: float):
        """Z-Phase Gate: |1> -> e^(i*theta)|1>."""
        phase = complex(math.cos(theta), math.sin(theta))
        self.beta *= phase

    def probabilities(self) -> tuple[float, float]:
        p0 = abs(self.alpha)**2
        p1 = abs(self.beta)**2
        return p0, p1

    def measure(self) -> int:
        """Kolaps gelombang probabilistik ke basis komputasi (|0> atau |1>)."""
        p0, _ = self.probabilities()
        outcome = 0 if random.random() < p0 else 1
        if outcome == 0:
            self.alpha = 1.0 + 0j
            self.beta = 0.0 + 0j
        else:
            self.alpha = 0.0 + 0j
            self.beta = 1.0 + 0j
        return outcome

    def render_bloch_ascii(self):
        p0, p1 = self.probabilities()
        bar_len = 30
        fill_0 = int(round(p0 * bar_len))
        fill_1 = bar_len - fill_0
        bar = f"{GREEN}{'#' * fill_0}{RESET}{MAGENTA}{'-' * fill_1}{RESET}"
        print(f"    Basis |0>: {p0*100:6.2f}% [{bar}] Basis |1>: {p1*100:6.2f}%")


class BellStatePair:
    """
    Simulasi 2-Qubit Entanglement: Menghasilkan Bell State (|00> + |11>) / sqrt(2).
    """
    def __init__(self):
        # State vector: [|00>, |01>, |10>, |11>]
        self.state = [1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 0.0 + 0j]

    def create_bell_state(self):
        # 1. Terapkan Hadamard pada Qubit-0
        # 2. Terapkan CNOT dengan Qubit-0 sebagai kontrol dan Qubit-1 sebagai target
        inv_sqrt2 = 1.0 / math.sqrt(2.0)
        self.state = [inv_sqrt2 + 0j, 0.0 + 0j, 0.0 + 0j, inv_sqrt2 + 0j]

    def measure_qubit(self, qubit_index: int) -> int:
        """
        Pengukuran pada salah satu qubit seketika mengolaps qubit pasangan (Quantum Non-locality).
        """
        # Probabilitas marginal
        p0 = abs(self.state[0])**2 + abs(self.state[1])**2
        outcome = 0 if random.random() < p0 else 1

        if qubit_index == 0:
            if outcome == 0:
                self.state = [1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 0.0 + 0j]
            else:
                self.state = [0.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j]
        else:
            if outcome == 0:
                self.state = [1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 0.0 + 0j]
            else:
                self.state = [0.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j]

        return outcome

    def read_collapsed_partner(self) -> int:
        if abs(self.state[0]) > 0.99:
            return 0
        elif abs(self.state[3]) > 0.99:
            return 1
        return -1


class SpikingNeuronLIF:
    """
    Simulasi Komputasi Neuromorphic: Leaky Integrate-and-Fire (LIF) Neuron Model.
    Menghitung integrasi muatan membran secara event-driven / time-step diskret.
    """
    def __init__(self, v_rest: float = -70.0, v_thresh: float = -50.0, v_reset: float = -75.0, tau: float = 10.0):
        self.v_rest = v_rest
        self.v_thresh = v_thresh
        self.v_reset = v_reset
        self.tau = tau
        self.v = v_rest

    def step(self, current_input: float, dt: float = 1.0) -> bool:
        dv = ((self.v_rest - self.v) + current_input * 1.5) * (dt / self.tau)
        self.v += dv
        if self.v >= self.v_thresh:
            self.v = self.v_reset
            return True  # Spike terpancar!
        return False


def run_quantum_superposition_demo():
    header("Simulasi 1: Qubit Superposisi & Hadamard Transform")
    q = QuantumState(alpha=1.0, beta=0.0)
    print(f"  {YELLOW}State Awal Qubit (|0>):{RESET}")
    q.render_bloch_ascii()

    print(f"\n  {CYAN}>>> Menerapkan Hadamard Gate H...{RESET}")
    time.sleep(0.4)
    q.apply_hadamard()
    print(f"  {YELLOW}State Superposisi (|0> + |1>) / sqrt(2):{RESET}")
    q.render_bloch_ascii()

    trials = 1000
    counts = {0: 0, 1: 0}
    for _ in range(trials):
        # Salin state superposisi dan ukur
        sample_q = QuantumState(alpha=q.alpha, beta=q.beta)
        res = sample_q.measure()
        counts[res] += 1

    print(f"\n  {BOLD}Hasil Monte Carlo {trials} Kali Pengukuran Kolaps Gelombang:{RESET}")
    print(f"    Basis |0>: {GREEN}{counts[0]} ({counts[0]/trials*100:.1f}%){RESET}")
    print(f"    Basis |1>: {MAGENTA}{counts[1]} ({counts[1]/trials*100:.1f}%){RESET}")


def run_bell_state_demo():
    header("Simulasi 2: Entanglement Bell State (EPR Pair)")
    print(f"  {DIM}Mempersiapkan sepasang qubit terjerat (entangled): (|00> + |11>) / sqrt(2)...{RESET}")
    bell = BellStatePair()
    bell.create_bell_state()
    time.sleep(0.3)

    print(f"  {CYAN}Qubit Alice dan Qubit Bob kini terjerat dalam jarak tak berhingga.{RESET}")
    alice_measure = bell.measure_qubit(0)
    print(f"  Alice melakukan pengukuran pada Qubit-A -> {BOLD}{GREEN}|{alice_measure}>{RESET}")

    bob_partner = bell.read_collapsed_partner()
    print(f"  Bob memeriksa Qubit-B seketika (Wavefunction Collapse) -> {BOLD}{CYAN}|{bob_partner}>{RESET}")

    assert alice_measure == bob_partner, "Pelanggaran korelasi kuantum entanglement!"
    print(f"  {YELLOW}[KORELASI 100%]{RESET} State collapse terjadi secara simultan tanpa komunikasi klasik.\n")


def run_neuromorphic_demo():
    header("Simulasi 3: Komputasi Neuromorphic (Spiking Neuron LIF)")
    neuron = SpikingNeuronLIF()
    timesteps = 25
    print(f"  {DIM}Memberikan injeksi stimulus arus sinaptik konstan (I_syn = 25.0 mA)...{RESET}\n")

    spikes_count = 0
    for t in range(timesteps):
        input_current = 24.0 if t >= 3 else 0.0
        spiked = neuron.step(input_current)
        spike_marker = f"{RED}{BOLD}* SPIKE! *{RESET}" if spiked else f"{DIM}.{RESET}"
        if spiked:
            spikes_count += 1
        v_bar = int(max(0, (neuron.v + 80) / 40 * 20))
        bar_viz = f"[{'=' * v_bar}{' ' * (20 - v_bar)}]"
        print(f"  T={t:02d} | V_mem={neuron.v:6.2f} mV {bar_viz} {spike_marker}")
        time.sleep(0.05)

    print(f"\n  Total Spikes dibangkitkan: {BOLD}{GREEN}{spikes_count}{RESET} dari {timesteps} timesteps.")
    print(f"  Efisiensi energi neuromorphic: komputasi hanya aktif saat event spike terpicu.")


def interactive_menu():
    while True:
        header("LAB EXERCISE BAB 10: ADVANCED COMPUTING FOUNDATIONS")
        print(f"  {CYAN}1.{RESET} Simulasi Qubit Superposition & Hadamard Gate")
        print(f"  {CYAN}2.{RESET} Simulasi Kuantum Entanglement Bell Pair")
        print(f"  {CYAN}3.{RESET} Simulasi Neuromorphic Spiking Neuron (LIF)")
        print(f"  {CYAN}4.{RESET} Jalankan Seluruh Pengujian Otomatis (Benchmark)")
        print(f"  {RED}0.{RESET} Keluar")
        print()

        try:
            choice = input(f"{BOLD}Pilih menu [0-4]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            run_quantum_superposition_demo()
        elif choice == "2":
            run_bell_state_demo()
        elif choice == "3":
            run_neuromorphic_demo()
        elif choice == "4":
            run_quantum_superposition_demo()
            run_bell_state_demo()
            run_neuromorphic_demo()
            print(f"\n{BOLD}{GREEN}Seluruh demonstrasi berhasil dieksekusi dengan sempurna.{RESET}\n")
        elif choice == "0":
            print(f"{YELLOW}Selesai. Selamat bereksplorasi di ranah komputasi masa depan!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_quantum_superposition_demo()
        run_bell_state_demo()
        run_neuromorphic_demo()
    else:
        interactive_menu()
