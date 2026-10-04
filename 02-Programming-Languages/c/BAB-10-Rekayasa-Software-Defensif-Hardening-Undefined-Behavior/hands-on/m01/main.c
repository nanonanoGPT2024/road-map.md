#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>

#define MAX_PAYLOAD_CAPACITY 4096

typedef enum {
    PARSER_OK = 0,
    PARSER_ERR_INVALID_ARGUMENT = -1,
    PARSER_ERR_BUFFER_OVERFLOW  = -2,
    PARSER_ERR_INTEGER_WRAPPING = -3,
    PARSER_ERR_CORRUPT_PAYLOAD  = -4
} ParserStatus_t;

typedef struct {
    uint8_t  payload_buffer[MAX_PAYLOAD_CAPACITY];
    size_t   actual_size;
} PacketStorage_t;

/**
 * @brief Memvalidasi dan mengekstrak payload dari raw network stream
 * secara aman dari underflow, overflow, dan pointer decay exploitation.
 */
ParserStatus_t parse_network_payload(
    const uint8_t *const raw_packet,
    const size_t raw_packet_total_size,
    const size_t payload_offset,
    const size_t payload_length,
    PacketStorage_t *const out_storage
) {
    // Contract Check 1: Validasi Pointer Nullitas
    if (raw_packet == NULL || out_storage == NULL) {
        return PARSER_ERR_INVALID_ARGUMENT;
    }

    // Contract Check 2: Verifikasi Batas Input Mutlak
    if (raw_packet_total_size == 0 || payload_length == 0) {
        return PARSER_ERR_INVALID_ARGUMENT;
    }

    // Contract Check 3: Deteksi Integer Overflow pada Aritmatika Penjumlahan Batas
    // Aturan C: Kita harus memeriksa (A + B > C) dengan cara (A > C - B)
    if (payload_offset > raw_packet_total_size) {
        return PARSER_ERR_BUFFER_OVERFLOW;
    }

    if (payload_length > (raw_packet_total_size - payload_offset)) {
        // Terjadi buffer over-read pada packet input
        return PARSER_ERR_BUFFER_OVERFLOW;
    }

    // Contract Check 4: Verifikasi Kapasitas Buffer Destinasi
    if (payload_length > MAX_PAYLOAD_CAPACITY) {
        return PARSER_ERR_BUFFER_OVERFLOW;
    }

    // Sanitasi Memori Destinasi Sebelum Salin
    memset(out_storage->payload_buffer, 0, sizeof(out_storage->payload_buffer));

    // Pointer Arithmetic Aman: Dipastikan dalam boundary [raw_packet, raw_packet + raw_packet_total_size]
    const uint8_t *const source_ptr = raw_packet + payload_offset;

    // Memcpy Terproteksi
    memcpy(out_storage->payload_buffer, source_ptr, payload_length);
    out_storage->actual_size = payload_length;

    return PARSER_OK;
}

// Simulasi Pengujian Defensif
int main(void) {
    uint8_t simulated_wire[64];
    memset(simulated_wire, 0xAB, sizeof(simulated_wire));
    
    PacketStorage_t safe_storage;
    ParserStatus_t status;

    printf("[TEST 1] Injeksi Integer Overflow Offset...\n");
    // Mensimulasikan data offset masif dari paket jahat
    size_t malicious_offset = SIZE_MAX - 10;
    size_t malicious_len = 20;

    status = parse_network_payload(simulated_wire, sizeof(simulated_wire), 
                                   malicious_offset, malicious_len, &safe_storage);

    if (status != PARSER_OK) {
        printf(" -> Berhasil ditangkal dengan kode error: %d\n", status);
    } else {
        printf(" -> GAGAL: Exploit tembus!\n");
        return 1;
    }

    printf("[TEST 2] Injeksi Buffer Over-read Lengkap...\n");
    status = parse_network_payload(simulated_wire, sizeof(simulated_wire), 
                                   50, 20, &safe_storage); // 50 + 20 = 70 > 64

    if (status == PARSER_ERR_BUFFER_OVERFLOW) {
        printf(" -> Berhasil ditangkal: Out-of-Bounds deteksi akurat.\n");
    } else {
        printf(" -> GAGAL: OOB lolos!\n");
        return 1;
    }

    printf("[TEST 3] Jalur Normal Operasional...\n");
    status = parse_network_payload(simulated_wire, sizeof(simulated_wire), 
                                   10, 32, &safe_storage);

    if (status == PARSER_OK && safe_storage.actual_size == 32) {
        printf(" -> Sukses mengekstrak paket secara aman.\n");
    } else {
        printf(" -> GAGAL: Valid packet ditolak.\n");
        return 1;
    }

    return 0;
}
