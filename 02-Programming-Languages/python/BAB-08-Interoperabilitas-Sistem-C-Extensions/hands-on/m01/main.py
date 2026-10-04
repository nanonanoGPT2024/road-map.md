import time
import os
import bytearray
import batch_crypto

def generate_telemetry_batch(num_packets: int, packet_size: int) -> bytearray:
    # Mengalokasikan blok memori berturut-turut mentah di CPython
    print(f"Allocating contiguous memory for {num_packets} packets ({num_packets * packet_size / (1024 * 1024):.2f} MB)...")
    return bytearray(os.urandom(num_packets * packet_size))

def main():
    PACKET_SIZE = 512
    NUM_PACKETS = 2_000_000  # Total ~1024 MB Memori contiguous
    XOR_KEY = 0x5A

    raw_batch = generate_telemetry_batch(NUM_PACKETS, PACKET_SIZE)

    print("Executing native multi-threaded batch transform (GIL Released)...")
    start_time = time.perf_counter()

    # Operasi in-place: Tanpa alokasi baru, referensi pointer langsung ke bytearray
    batch_crypto.process_batch(raw_batch, XOR_KEY, PACKET_SIZE)

    elapsed = time.perf_counter() - start_time
    throughput_mb = (len(raw_batch) / (1024 * 1024)) / elapsed
    packets_per_sec = NUM_PACKETS / elapsed

    print(f"Execution Completed in: {elapsed:.4f} seconds")
    print(f"Throughput: {throughput_mb:.2f} MB/s")
    print(f"Packet Processing Velocity: {packets_per_sec:,.0f} packets/second")

if __name__ == "__main__":
    main()
