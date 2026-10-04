#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdalign.h>

// Definisi Opcode Telemetri
typedef enum : uint8_t {
    OPCODE_ENVIRONMENTAL = 0x01,
    OPCODE_SYSTEM_STATUS = 0x02,
    OPCODE_CRITICAL_ALERT = 0x03
} TelemetryOpcode;

// Control Flags Header menggunakan bit-field (1 Byte)
typedef struct {
    uint8_t is_encrypted : 1;
    uint8_t priority     : 2;
    uint8_t version      : 5;
} PacketHeaderFlags;

// Payload 1: Environmental (8 Bytes)
typedef struct {
    int16_t  temperature_celsius; // Skala 0.01 C
    uint16_t humidity_percent;    // Skala 0.01 %
    uint32_t atmospheric_pa;      // Pascal
} EnvironmentalPayload;

// Payload 2: System Status (8 Bytes)
typedef struct {
    uint32_t uptime_seconds;
    uint16_t battery_millivolts;
    uint8_t  cpu_load_percent;
    uint8_t  reserved;
} SystemStatusPayload;

// Payload 3: Critical Alert (8 Bytes)
typedef struct {
    uint32_t alert_code;
    uint32_t fault_address;
} CriticalAlertPayload;

// Discriminative Tagged Record: Ukuran union fix 8 bita
typedef union {
    EnvironmentalPayload env;
    SystemStatusPayload  sys;
    CriticalAlertPayload alert;
    uint8_t              raw_bytes[8];
} TelemetryPayload;

// Paket Lengkap yang diterima (Strict Memory Aligned Header)
typedef struct {
    PacketHeaderFlags flags;
    TelemetryOpcode   opcode;
    uint16_t          sequence_number;
    uint32_t          payload_crc;
    TelemetryPayload  data;
} TelemetryFrame;

// Simple Checksum Function (CRC-32 Placeholder: XOR Checksum untuk contoh ini)
static uint32_t calculate_checksum(const uint8_t *data, size_t len) {
    uint32_t checksum = 0xEDB88320;
    for (size_t i = 0; i < len; ++i) {
        checksum ^= (uint32_t)data[i];
        for (int j = 0; j < 8; ++j) {
            checksum = (checksum >> 1) ^ (0xEDB88320 & (-(checksum & 1)));
        }
    }
    return checksum;
}

// Zero-copy processing function
void process_packet(const uint8_t *raw_stream, size_t stream_size) {
    if (stream_size < sizeof(TelemetryFrame)) {
        fprintf(stderr, "[ERROR] Paket truncate: Ukuran %zu bita < Minimum %zu bita\n", 
                stream_size, sizeof(TelemetryFrame));
        return;
    }

    // Hindari unaligned direct casting! Salin via memcpy atau gunakan pointer aligned
    TelemetryFrame frame;
    memcpy(&frame, raw_stream, sizeof(TelemetryFrame));

    // Validasi Integritas Payload via CRC
    uint32_t computed_crc = calculate_checksum(frame.data.raw_bytes, sizeof(TelemetryPayload));
    if (computed_crc != frame.payload_crc) {
        fprintf(stderr, "[ALERT] Corrupt CRC: Dihitung=0x%08X, Didapat=0x%08X\n", 
                computed_crc, frame.payload_crc);
        return;
    }

    printf("=== DITERIMA TELEMETRY FRAME [Seq: %u] ===\n", frame.sequence_number);
    printf("Header: Ver=%u, Priority=%u, Encrypted=%s\n", 
           frame.flags.version, frame.flags.priority, 
           frame.flags.is_encrypted ? "YES" : "NO");

    switch (frame.opcode) {
        case OPCODE_ENVIRONMENTAL:
            printf("Payload Type: Environmental\n");
            printf("  Suhu: %.2f C\n", frame.data.env.temperature_celsius / 100.0f);
            printf("  Kelembaban: %.2f %%\n", frame.data.env.humidity_percent / 100.0f);
            printf("  Tekanan: %u Pa\n", frame.data.env.atmospheric_pa);
            break;

        case OPCODE_SYSTEM_STATUS:
            printf("Payload Type: System Status\n");
            printf("  Uptime: %u detik\n", frame.data.sys.uptime_seconds);
            printf("  Baterai: %u mV\n", frame.data.sys.battery_millivolts);
            printf("  CPU Load: %u %%\n", frame.data.sys.cpu_load_percent);
            break;

        case OPCODE_CRITICAL_ALERT:
            printf("[WARNING] Payload Type: CRITICAL ALERT\n");
            printf("  Alert Code: 0x%08X\n", frame.data.alert.alert_code);
            printf("  Fault Addr: 0x%08X\n", frame.data.alert.fault_address);
            break;

        default:
            fprintf(stderr, "[ERROR] Opcode tidak dikenal: 0x%02X\n", frame.opcode);
            break;
    }
    printf("----------------------------------------\n\n");
}

int main(void) {
    // Simulasi pembuatan paket dari transmisi jaringan (Little Endian System)
    TelemetryFrame tx_frame;
    memset(&tx_frame, 0, sizeof(TelemetryFrame));

    // Siapkan Header
    tx_frame.flags.version = 1;
    tx_frame.flags.priority = 3;
    tx_frame.flags.is_encrypted = 0;
    tx_frame.opcode = OPCODE_ENVIRONMENTAL;
    tx_frame.sequence_number = 1024;

    // Siapkan Data
    tx_frame.data.env.temperature_celsius = 2845; // 28.45 C
    tx_frame.data.env.humidity_percent = 6520;    // 65.20 %
    tx_frame.data.env.atmospheric_pa = 101325;    // 101325 Pa

    // Hitung Checksum
    tx_frame.payload_crc = calculate_checksum(tx_frame.data.raw_bytes, sizeof(TelemetryPayload));

    // Simulasikan raw buffer transmisi biner
    uint8_t binary_buffer[sizeof(TelemetryFrame)];
    memcpy(binary_buffer, &tx_frame, sizeof(TelemetryFrame));

    // Parsing frame valid
    process_packet(binary_buffer, sizeof(binary_buffer));

    // Simulasi paket korup (Data diubah secara sengaja di transmisi)
    binary_buffer[12] ^= 0xFF; // Merusak bita payload
    process_packet(binary_buffer, sizeof(binary_buffer));

    return 0;
}
