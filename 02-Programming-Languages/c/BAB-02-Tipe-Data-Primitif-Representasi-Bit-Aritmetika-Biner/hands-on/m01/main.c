#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define PACKET_SYNC_BYTE        0xAA
#define PACKET_FRAME_SIZE       8
#define CRC16_POLYNOMIAL        0x1021

typedef struct {
    bool     fault_warning;
    uint8_t  operating_mode;
    uint8_t  protocol_version;
    float    temperature_c;
    float    humidity_pct;
} TelemetryData;

/**
 * Menghitung CRC16-CCITT (False) secara bitwise deterministik.
 */
static uint16_t calculate_crc16(const uint8_t *data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; ++i) {
        crc ^= ((uint16_t)data[i] << 8);
        for (uint8_t bit = 0; bit < 8; ++bit) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ CRC16_POLYNOMIAL;
            } else {
                crc = (crc << 1);
            }
        }
    }
    return crc;
}

/**
 * Melakukan parsing frame biner telemetri secara aman.
 * Menghindari struct memory casting guna mencegah padding issues & undefined behavior.
 */
bool parse_telemetry_packet(const uint8_t *stream_buffer, size_t buffer_len, TelemetryData *out_data) {
    if (stream_buffer == NULL || out_data == NULL) {
        return false;
    }

    if (buffer_len < PACKET_FRAME_SIZE) {
        return false; // Buffer underrun
    }

    // 1. Verifikasi Header Sync Byte
    if (stream_buffer[0] != PACKET_SYNC_BYTE) {
        return false; // Desinkronisasi protokol
    }

    // 2. Verifikasi Integritas Data via Checksum (CRC-16)
    uint16_t packet_crc = ((uint16_t)stream_buffer[6] << 8) | (uint16_t)stream_buffer[7];
    uint16_t computed_crc = calculate_crc16(stream_buffer, 6);
    
    if (packet_crc != computed_crc) {
        return false; // Data corrupt / bit flip
    }

    // 3. Dekonstruksi Bitfield Flag (Byte 1)
    uint8_t flags_byte = stream_buffer[1];
    out_data->fault_warning    = (flags_byte >> 7) & 0x01;
    out_data->operating_mode   = (flags_byte >> 4) & 0x07; // Mask 3-bit: 0b111 = 0x07
    out_data->protocol_version = flags_byte & 0x0F;        // Mask 4-bit: 0b1111 = 0x0F

    // 4. Rekonstruksi Temperature (Signed 16-bit Big-Endian)
    // Hindari undefined behavior sign extension dengan parsing ke unsigned terlebih dahulu
    uint16_t raw_temp_be = ((uint16_t)stream_buffer[2] << 8) | (uint16_t)stream_buffer[3];
    int16_t raw_temp_signed;
    // Explicitly copy ke signed int16_t untuk memetakan komplemen dua
    memcpy(&raw_temp_signed, &raw_temp_be, sizeof(raw_temp_signed));
    out_data->temperature_c = (float)raw_temp_signed / 100.0f;

    // 5. Rekonstruksi Humidity (Unsigned 16-bit Big-Endian)
    uint16_t raw_hum_be = ((uint16_t)stream_buffer[4] << 8) | (uint16_t)stream_buffer[5];
    out_data->humidity_pct = (float)raw_hum_be / 100.0f;

    return true;
}

int main(void) {
    // Simulasi Paket Transmisi Masuk dari Jaringan:
    // Sync: 0xAA
    // Flags: 0xA2 -> Binary: 1 010 0010 (Fault: 1, Mode: 2 [Boost], Ver: 2)
    // Raw Temp: 0xFE 0x0C -> Nilai signed -500 (desimal) -> -5.00 Celcius
    // Raw Hum:  0x1D 0x4C -> Nilai unsigned 7500 (desimal) -> 75.00 %
    // CRC-16 dihitung manual/komputer untuk payload di atas: 0x937B
    uint8_t mock_network_frame[PACKET_FRAME_SIZE] = {
        0xAA, 
        0xA2, 
        0xFE, 0x0C, 
        0x1D, 0x4C, 
        0x93, 0x7B
    };

    TelemetryData current_metrics;
    
    printf("Mencoba parsing frame biner (%d byte)...\n", PACKET_FRAME_SIZE);
    if (parse_telemetry_packet(mock_network_frame, sizeof(mock_network_frame), &current_metrics)) {
        printf("[SUCCESS] Telemetri Terbaca Valid:\n");
        printf(" - Protocol Version : %u\n", current_metrics.protocol_version);
        printf(" - Operating Mode    : %u\n", current_metrics.operating_mode);
        printf(" - Fault Status      : %s\n", current_metrics.fault_warning ? "ACTIVE FAULT" : "NORMAL");
        printf(" - Temperature       : %.2f degC\n", current_metrics.temperature_c);
        printf(" - Humidity          : %.2f %%\n", current_metrics.humidity_pct);
    } else {
        printf("[ERROR] Paket tidak valid (Sync mismatch / CRC Error / Truncated).\n");
    }

    return 0;
}
