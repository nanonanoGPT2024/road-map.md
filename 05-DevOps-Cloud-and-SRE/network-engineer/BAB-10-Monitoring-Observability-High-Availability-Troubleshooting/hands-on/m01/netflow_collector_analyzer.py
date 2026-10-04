#!/usr/bin/env python3
"""
NetFlow v9 / IPFIX Minimal Collector & Analyzer
Platform Network Reliability Engineering - Core Curriculum

Skrip ini adalah parser dan analyzer UDP flow records mandiri (NetFlow v9 & IPFIX)
yang dirancang untuk debugging paket telemetri data-plane, mendeteksi flow microburst,
dan menghitung metriks 5-tuple real-time tanpa dependensi library eksternal.
"""

import socket
import struct
import sys
import time
from collections import defaultdict
from datetime import datetime

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 2055
BUFFER_SIZE = 65535

# Storage untuk Template NetFlow v9: { (source_ip, template_id): [ (field_type, field_length), ... ] }
TEMPLATES = {}

# Counter internal analitik
STATS = {
    "packets_received": 0,
    "flows_parsed": 0,
    "bytes_total": 0,
    "top_talkers": defaultdict(int),
}

def ip_to_str(ip_int):
    """Konversi integer 32-bit IPv4 ke string titik desimal."""
    return socket.inet_ntoa(struct.pack("!I", ip_int))

def parse_netflow_v9(data, client_addr):
    """
    Parser biner untuk paket NetFlow v9 (RFC 3954).
    Header Format:
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |            Version            |             Count             |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                         sysUptime                             |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                       unix_secs                               |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                       package_seq                             |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                        source_id                              |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
    if len(data) < 20:
        return

    version, count, uptime, unix_secs, seq_num, source_id = struct.unpack("!HHIIII", data[:20])
    if version != 9:
        return

    offset = 20
    source_host = client_addr[0]

    for _ in range(count):
        if offset >= len(data):
            break

        flowset_id, flowset_len = struct.unpack("!HH", data[offset:offset+4])
        flowset_data = data[offset+4 : offset+flowset_len]
        offset += flowset_len

        # FlowSet ID 0 = Template FlowSet
        if flowset_id == 0:
            t_offset = 0
            while t_offset < len(flowset_data):
                if t_offset + 4 > len(flowset_data):
                    break
                template_id, field_count = struct.unpack("!HH", flowset_data[t_offset:t_offset+4])
                t_offset += 4
                fields = []
                for _ in range(field_count):
                    if t_offset + 4 > len(flowset_data):
                        break
                    f_type, f_len = struct.unpack("!HH", flowset_data[t_offset:t_offset+4])
                    fields.append((f_type, f_len))
                    t_offset += 4
                TEMPLATES[(source_host, template_id)] = fields
                print(f"[TEMPLATE] Host: {source_host} Registered Template ID: {template_id} with {field_count} fields.")

        # FlowSet ID > 255 = Data FlowSet
        elif flowset_id >= 256:
            template_key = (source_host, flowset_id)
            if template_key not in TEMPLATES:
                # Belum menerima template definition
                continue

            template_fields = TEMPLATES[template_key]
            record_size = sum(f[1] for f in template_fields)
            if record_size == 0:
                continue

            d_offset = 0
            while d_offset + record_size <= len(flowset_data):
                record_raw = flowset_data[d_offset : d_offset + record_size]
                d_offset += record_size

                flow_info = {}
                r_offset = 0
                for f_type, f_len in template_fields:
                    val_bytes = record_raw[r_offset : r_offset + f_len]
                    r_offset += f_len

                    # Standard NetFlow v9 Field Types (RFC 3954)
                    # 1: IN_BYTES, 2: IN_PKTS, 4: PROTOCOL, 7: L4_SRC_PORT, 8: IPV4_SRC_ADDR, 
                    # 11: L4_DST_PORT, 12: IPV4_DST_ADDR, 6: TCP_FLAGS
                    if f_len == 1:
                        val = struct.unpack("!B", val_bytes)[0]
                    elif f_len == 2:
                        val = struct.unpack("!H", val_bytes)[0]
                    elif f_len == 4:
                        val = struct.unpack("!I", val_bytes)[0]
                    else:
                        val = int.from_bytes(val_bytes, byteorder='big')

                    flow_info[f_type] = val

                process_flow_record(flow_info)

def process_flow_record(flow):
    """Analisis metrik traffic dari single flow record."""
    STATS["flows_parsed"] += 1

    src_ip = ip_to_str(flow.get(8, 0))
    dst_ip = ip_to_str(flow.get(12, 0))
    src_port = flow.get(7, 0)
    dst_port = flow.get(11, 0)
    proto = flow.get(4, 0)
    bytes_count = flow.get(1, 0)
    packets_count = flow.get(2, 0)
    tcp_flags = flow.get(6, 0)

    STATS["bytes_total"] += bytes_count
    talker_key = f"{src_ip}:{src_port} -> {dst_ip}:{dst_port} (Proto: {proto})"
    STATS["top_talkers"][talker_key] += bytes_count

    # Deteksi anomali volume per flow (> 10MB dalam 1 flow)
    if bytes_count > 10 * 1024 * 1024:
        print(f"\n[ALERT - HIGH VOLUME FLOW] Detected {bytes_count / (1024*1024):.2f} MB in single flow:")
        print(f"       Path: {talker_key} | Packets: {packets_count} | TCP Flags: {hex(tcp_flags)}")

def render_dashboard():
    """Tampilkan live console stats periodik."""
    print("\033[2J\033[H", end="") # Clear screen & home cursor
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"==================================================================")
    print(f"      NETFLOW V9 / IPFIX NRE ANALYZER ENGINE - {now}        ")
    print(f"==================================================================")
    print(f"Packets Processed  : {STATS['packets_received']}")
    print(f"Total Flows Parsed : {STATS['flows_parsed']}")
    print(f"Total Volume Monitored : {STATS['bytes_total'] / (1024*1024):.2f} MB")
    print(f"Active Templates   : {len(TEMPLATES)}")
    print(f"------------------------------------------------------------------")
    print(f"TOP TALKERS (BY VOLUME):")
    sorted_talkers = sorted(STATS["top_talkers"].items(), key=lambda x: x[1], reverse=True)[:5]
    for idx, (conn, vol) in enumerate(sorted_talkers, 1):
        print(f" {idx}. {conn} | Transferred: {vol / 1024:.2f} KB")
    print(f"==================================================================")
    print(f"Press Ctrl+C to stop listening.")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((LISTEN_IP, LISTEN_PORT))
    except PermissionError:
        print(f"[ERROR] Port {LISTEN_PORT} memerlukan izin administrator/root!")
        sys.exit(1)
    except OSError as e:
        print(f"[ERROR] Gagal melakukan bind socket: {e}")
        sys.exit(1)

    print(f"[*] NetFlow Analyzer Daemon mendengarkan pada UDP {LISTEN_IP}:{LISTEN_PORT}...")
    last_display = time.time()

    try:
        while True:
            data, client_addr = sock.recvfrom(BUFFER_SIZE)
            STATS["packets_received"] += 1
            parse_netflow_v9(data, client_addr)

            if time.time() - last_display > 2.0:
                render_dashboard()
                last_display = time.time()

    except KeyboardInterrupt:
        print("\n[*] Menghentikan collector analyzer. Ringkasan akhir:")
        print(f"Total paket diterima: {STATS['packets_received']}")
        print(f"Total volume terhitung: {STATS['bytes_total']} bytes.")
        sock.close()

if __name__ == "__main__":
    main()