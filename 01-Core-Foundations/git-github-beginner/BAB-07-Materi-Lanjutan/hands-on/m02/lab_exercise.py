#!/usr/bin/env python3
"""
Lab Exercise: Git Remote Protocol Plumbing & Wire Negotiation Simulation
Topic: git-github-beginner | Category: 01-Core-Foundations
Chapter: 07 (Kolaborasi Jarak Jauh / Remote Repositories & Protocol Plumbing) - Modul 02

Deskripsi:
Skrip ini mensimulasikan protokol internal Git (Git Wire Protocol / Smart Transfer Protocol)
pada level plumbing. Mensimulasikan format framing pkt-line, advertising refs, negosiasi
objek (want/have negotiation) menggunakan directed acyclic graph (DAG) komit, dan
pembuatan payload packfile antar Remote Server dan Local Client.
"""

import io
import sys
import time
import hashlib
from typing import Dict, List, Set, Optional, Tuple

# Terminal ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"


# ==============================================================================
# 1. GIT WIRE PROTOCOL: PKT-LINE FRAMING UTILITIES
# ==============================================================================

class PktLine:
    """
    Implementasi Git Pkt-line (Packet-Line Format).
    Format: 4-byte hex prefix penanda total panjang paket (termasuk 4 byte header).
    Khusus: '0000' merepresentasikan flush-pkt (pemisah segmen/akhir stream).
    """

    FLUSH_PKT = b"0000"

    @staticmethod
    def encode(payload: Optional[bytes]) -> bytes:
        """Mengemas payload bytes ke dalam frame pkt-line standar Git."""
        if payload is None:
            return PktLine.FLUSH_PKT
        
        # Panjang paket = 4 byte length header + panjang payload
        total_len = len(payload) + 4
        if total_len > 65524:
            raise ValueError("Payload melebihi kapasitas maksimum pkt-line (65520 bytes)")
        
        header = f"{total_len:04x}".encode("ascii")
        return header + payload

    @staticmethod
    def decode_packet(stream: io.BytesIO) -> Optional[bytes]:
        """
        Membaca dan mem-parsing 1 frame pkt-line dari byte stream.
        Mengembalikan None jika membaca flush-pkt ('0000').
        """
        header = stream.read(4)
        if not header or len(header) < 4:
            return None
        
        if header == PktLine.FLUSH_PKT:
            return None
        
        try:
            length = int(header.decode("ascii"), 16)
        except ValueError:
            raise ValueError(f"Header pkt-line korup: {header!r}")
        
        payload_len = length - 4
        payload = stream.read(payload_len)
        return payload


# ==============================================================================
# 2. INTERNAL OBJECT STORE & DAG COMMITS
# ==============================================================================

class MockCommit:
    """Representasi objek Commit dalam Graph Git."""
    def __init__(self, message: str, parents: List[str] = None):
        self.message = message
        self.parents = parents or []
        # Generate simulated SHA-1 hash
        hasher = hashlib.sha1()
        hasher.update(message.encode("utf-8"))
        for p in self.parents:
            hasher.update(p.encode("utf-8"))
        self.oid = hasher.hexdigest()

    def __repr__(self) -> str:
        return f"Commit({self.oid[:7]}, '{self.message}')"


# ==============================================================================
# 3. REMOTE SERVER ENGINE (git-upload-pack daemon)
# ==============================================================================

class GitRemoteServer:
    """
    Mensimulasikan Git Remote Server yang menangani layanan upload-pack
    untuk operasi fetch/pull client.
    """
    def __init__(self, name: str):
        self.name = name
        self.objects: Dict[str, MockCommit] = {}
        self.refs: Dict[str, str] = {}
        self.capabilities = ["multi_ack", "side-band-64k", "ofs-delta", "agent=git/custom-lab"]

    def add_commit(self, message: str, parents: List[str] = None) -> MockCommit:
        commit = MockCommit(message, parents)
        self.objects[commit.oid] = commit
        return commit

    def advertise_refs(self) -> bytes:
        """
        Fase 1: Server mengirim daftar referensi (branches/tags) beserta kapabilitasnya.
        Format baris pertama menyertakan capabilities yang dipisahkan NULL-byte ('\0').
        """
        buf = io.BytesIO()
        first_ref = True

        for ref_name, oid in sorted(self.refs.items()):
            if first_ref:
                caps = " ".join(self.capabilities)
                line = f"{oid} {ref_name}\0{caps}\n".encode("utf-8")
                buf.write(PktLine.encode(line))
                first_ref = False
            else:
                line = f"{oid} {ref_name}\n".encode("utf-8")
                buf.write(PktLine.encode(line))

        buf.write(PktLine.encode(None))  # Flush-pkt
        return buf.getvalue()

    def service_upload_pack(self, request_payload: bytes) -> bytes:
        """
        Fase 2: Server memproses negosiasi want/have dari client,
        mengidentifikasi delta commit, dan membungkus packfile data.
        """
        stream = io.BytesIO(request_payload)
        wants: Set[str] = set()
        haves: Set[str] = set()

        # Parse request wants & haves
        while True:
            pkt = PktLine.decode_packet(stream)
            if pkt is None:
                break
            line = pkt.decode("utf-8").strip()
            if line.startswith("want "):
                wants.add(line.split()[1])
            elif line.startswith("have "):
                haves.add(line.split()[1])

        response_buf = io.BytesIO()

        # Negosiasi: Server mencari ancestor bersama
        common_ancestor = None
        for have in haves:
            if have in self.objects:
                common_ancestor = have
                # Kirim sinyal ACK
                ack_line = f"ACK {have}\n".encode("utf-8")
                response_buf.write(PktLine.encode(ack_line))
                break

        if not common_ancestor and haves:
            response_buf.write(PktLine.encode(b"NAK\n"))

        response_buf.write(PktLine.encode(None))  # Flush setelah negosiasi ACK/NAK

        # Hitung Delta Objek (Koleksi commit yang ada di 'want' tapi belum ada di 'have')
        missing_commits = self._resolve_object_closure(wants, haves)
        
        # Simulasikan pengiriman Data Packfile melalui protocol multiplexing
        pack_header = f"PACKFILE: Contains {len(missing_commits)} objects: " + \
                      ", ".join([c[:7] for c in missing_commits])
        response_buf.write(PktLine.encode(pack_header.encode("utf-8")))
        response_buf.write(PktLine.encode(None))

        return response_buf.getvalue()

    def _resolve_object_closure(self, wants: Set[str], haves: Set[str]) -> List[str]:
        """Menemukan seluruh objek yang perlu dikirim (DAG traversal)."""
        visited: Set[str] = set(haves)
        to_send: List[str] = []
        queue: List[str] = list(wants)

        while queue:
            curr = queue.pop(0)
            if curr in visited or curr not in self.objects:
                continue
            visited.add(curr)
            to_send.append(curr)
            queue.extend(self.objects[curr].parents)

        return to_send


# ==============================================================================
# 4. LOCAL CLIENT ENGINE (git-fetch plumbing)
# ==============================================================================

class GitLocalClient:
    """Mensimulasikan Git Client lokal yang melakukan sinkronisasi dengan remote."""
    def __init__(self):
        self.objects: Dict[str, MockCommit] = {}
        self.remote_tracking_refs: Dict[str, str] = {}
        self.local_branches: Dict[str, str] = {}

    def fetch_from_remote(self, server: GitRemoteServer):
        """Menjalankan full-cycle fetch handshake dan negosiasi Git wire protocol."""
        print(f"\n{BOLD}{CYAN}=== MEMULAI REMOTE FETCH PLUMBING: {server.name} ==={RESET}\n")

        # 1. Discovery / Ref Advertisement
        print(f"{YELLOW}[STEP 1] Menerima Discovery & Ref Advertisement dari Remote...{RESET}")
        raw_ad = server.advertise_refs()
        self._inspect_raw_stream(raw_ad)

        ad_stream = io.BytesIO(raw_ad)
        server_refs: Dict[str, str] = {}
        server_caps = []

        is_first = True
        while True:
            pkt = PktLine.decode_packet(ad_stream)
            if pkt is None:
                break
            decoded = pkt.decode("utf-8").strip()
            if is_first:
                ref_part, caps_part = decoded.split("\0")
                oid, ref_name = ref_part.split()
                server_caps = caps_part.split()
                server_refs[ref_name] = oid
                is_first = False
            else:
                oid, ref_name = decoded.split()
                server_refs[ref_name] = oid

        print(f"{GREEN}✓ Berhasil mem-parsing {len(server_refs)} refs & {len(server_caps)} capabilities.{RESET}")
        for ref, oid in server_refs.items():
            print(f"  - {ref} -> {oid[:7]}")

        # 2. Want / Have Negotiation Phase
        print(f"\n{YELLOW}[STEP 2] Membangun Negosiasi (Want / Have Negotiation)...{RESET}")
        req_buf = io.BytesIO()

        # Tentukan apa yang kita inginkan (Server ref berbeda dengan local tracking)
        wants: Set[str] = set()
        for ref_name, s_oid in server_refs.items():
            if self.remote_tracking_refs.get(ref_name) != s_oid:
                wants.add(s_oid)
                print(f"  * Mengirim {MAGENTA}want{RESET} {s_oid[:7]} ({ref_name})")
                req_buf.write(PktLine.encode(f"want {s_oid}\n".encode("utf-8")))

        if not wants:
            print(f"{GREEN}Semua branch remote sudah up-to-date! Tidak ada paket ditransfer.{RESET}")
            return

        req_buf.write(PktLine.encode(None))  # Flush want section

        # Kirim haves (commit lokal terakhir yang kita pegang)
        for b_name, l_oid in self.local_branches.items():
            print(f"  * Mengirim {CYAN}have{RESET} {l_oid[:7]} ({b_name})")
            req_buf.write(PktLine.encode(f"have {l_oid}\n".encode("utf-8")))

        req_buf.write(PktLine.encode(None))  # Akhiri negosiasi

        # 3. Transmisi ke Server & Respon Packfile
        print(f"\n{YELLOW}[STEP 3] Mengirim Negotiation Packet ke Remote Server...{RESET}")
        raw_request = req_buf.getvalue()
        self._inspect_raw_stream(raw_request)

        print(f"{YELLOW}[STEP 4] Server Memproses Slicing DAG & Mengirim Response...{RESET}")
        raw_response = server.service_upload_pack(raw_request)
        self._inspect_raw_stream(raw_response)

        # 4. Parsing Sinyal ACK / Pack Payload
        resp_stream = io.BytesIO(raw_response)
        while True:
            pkt = PktLine.decode_packet(resp_stream)
            if pkt is None:
                # Flush point
                continue
            line = pkt.decode("utf-8").strip()
            if line.startswith("ACK"):
                print(f"{GREEN}✓ Remote Server mengonfirmasi Ancestor Bersama: {BOLD}{line}{RESET}")
            elif line.startswith("NAK"):
                print(f"{RED}! Server mengembalikan NAK: Tidak ada ancestor bersama yang cocok.{RESET}")
            elif line.startswith("PACKFILE:"):
                print(f"{MAGENTA}✓ Payload Packfile diterima:{RESET} {line}")
                break

        # 5. Sinkronisasi Remote Tracking Branch Lokal
        print(f"\n{YELLOW}[STEP 5] Memperbarui Local Remote-Tracking References...{RESET}")
        for ref_name, s_oid in server_refs.items():
            old_oid = self.remote_tracking_refs.get(ref_name, "0000000")[:7]
            self.remote_tracking_refs[ref_name] = s_oid
            print(f"  [updated] {ref_name}: {old_oid} -> {s_oid[:7]}")

    def _inspect_raw_stream(self, data: bytes):
        """Utility untuk mendemonstrasikan inspeksi paket hexdump/wire frame."""
        print(f"{DIM}--- [WIRE RAW PACKETS DUMP ({len(data)} bytes)] ---")
        stream = io.BytesIO(data)
        while True:
            header = stream.read(4)
            if not header:
                break
            if header == PktLine.FLUSH_PKT:
                print(f"  {DIM}0000 [FLUSH-PKT]{RESET}")
                continue
            try:
                length = int(header.decode("ascii"), 16)
                content = stream.read(length - 4)
                print(f"  {CYAN}{header.decode('ascii')}{RESET} {content!r}")
            except Exception as e:
                print(f"  {RED}Malformed Packet: {e}{RESET}")
                break
        print(f"------------------------------------------------{RESET}")


# ==============================================================================
# 5. LAB DEMONSTRATION WORKFLOW
# ==============================================================================

def main():
    print(f"{BOLD}{MAGENTA}================================================================")
    print("   LAB: GIT REMOTE PLUMBING & SMART PROTOCOL NEGOTIATION")
    print(f"================================================================{RESET}")
    time.sleep(0.3)

    # 1. Setup Simulasi Remote Server DAG
    # Commit DAG Server: C1 -> C2 -> C3 -> C4 (refs/heads/main)
    #                            \-> C5 (refs/heads/feature)
    origin = GitRemoteServer("origin (git@github.com:core/lab-repo.git)")
    
    c1 = origin.add_commit("Initial Commit (C1)")
    c2 = origin.add_commit("Add Base Architecture (C2)", parents=[c1.oid])
    c3 = origin.add_commit("Implement Core Service (C3)", parents=[c2.oid])
    c4 = origin.add_commit("Production Release Prep (C4)", parents=[c3.oid])
    c5 = origin.add_commit("Feature Experimental Auth (C5)", parents=[c2.oid])

    origin.refs["refs/heads/main"] = c4.oid
    origin.refs["refs/heads/feature"] = c5.oid

    # 2. Setup Client Lokal
    # Client sebelumnya sudah memiliki C1 dan C2, namun tertinggal C3, C4, C5
    client = GitLocalClient()
    client.objects[c1.oid] = c1
    client.objects[c2.oid] = c2
    client.local_branches["refs/heads/main"] = c2.oid
    client.remote_tracking_refs["refs/heads/main"] = c2.oid

    print(f"\n{BOLD}[STATUS AWAL]{RESET}")
    print(f"Local tracking  : main @ {c2.oid[:7]} ('{c2.message}')")
    print(f"Remote upstream : main @ {c4.oid[:7]} ('{c4.message}')")
    print(f"Remote upstream : feature @ {c5.oid[:7]} ('{c5.message}')")

    # 3. Jalankan Fetch Pertama: Terjadi proses negosiasi Smart Protocol
    client.fetch_from_remote(origin)

    # 4. Jalankan Fetch Kedua: Demonstrasi idempotent ketika state sudah sama
    print(f"\n{BOLD}{CYAN}=== PENGUJIAN FETCH KEDUA (NO-OP VERIFICATION) ==={RESET}")
    client.fetch_from_remote(origin)

    print(f"\n{BOLD}{GREEN}✓ Lab plumbing simulasi protokol remote Git selesai secara sukses.{RESET}\n")


if __name__ == "__main__":
    main()