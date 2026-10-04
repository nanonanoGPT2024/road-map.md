/**
 * @file linear_arena.c
 * @brief Implementasi Linear Memory Arena Allocator Berbasis Alignment.
 * Standar: C11
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>

typedef struct {
    uint8_t* buffer;      /**< Pointer ke blok memori dasar */
    size_t   capacity;    /**< Total kapasitas arena dalam byte */
    size_t   offset;      /**< Titik alokasi saat ini */
} MemoryArena;

/**
 * @brief Menghitung nilai pointer berikutnya yang memenuhi kriteria alignment.
 * 
 * Menggunakan bitwise masking. Alignment HARUS merupakan perpangkatan dari dua (Power of 2).
 */
static uintptr_t align_forward(uintptr_t ptr, size_t alignment) {
    assert((alignment & (alignment - 1)) == 0 && "Alignment harus berupa power of 2");
    return (ptr + (alignment - 1)) & ~(alignment - 1);
}

/**
 * @brief Inisialisasi Memory Arena.
 */
bool arena_init(MemoryArena* arena, size_t capacity) {
    if (!arena || capacity == 0) return false;

    arena->buffer = (uint8_t*)malloc(capacity);
    if (!arena->buffer) {
        arena->capacity = 0;
        arena->offset = 0;
        return false;
    }

    arena->capacity = capacity;
    arena->offset = 0;
    return true;
}

/**
 * @brief Mengalokasikan blok memori baru dengan alignment spesifik.
 * 
 * @param arena Pointer ke instance arena
 * @param size Ukuran alokasi yang diminta
 * @param alignment Alignment boundary yang diwajibkan (misal 4, 8, 16, 64)
 * @return void* Pointer ke memori yang ter-align, atau NULL jika kapasitas habis.
 */
void* arena_alloc_align(MemoryArena* arena, size_t size, size_t alignment) {
    if (!arena || !arena->buffer || size == 0) return NULL;

    // 1. Tentukan alamat aktual absolut saat ini
    uintptr_t current_addr = (uintptr_t)(arena->buffer + arena->offset);

    // 2. Hitung alamat maju yang ter-align
    uintptr_t aligned_addr = align_forward(current_addr, alignment);

    // 3. Hitung padding yang terbuang demi mencapai alignment
    size_t padding = aligned_addr - current_addr;

    // 4. Periksa apakah memori mencukupi
    if (arena->offset + padding + size > arena->capacity) {
        return NULL; // Out of Memory pada Arena
    }

    // 5. Geser offset arena
    arena->offset += padding + size;

    // 6. Return alamat memori yang valid
    return (void*)aligned_addr;
}

/**
 * @brief Helper alokasi default (menggunakan alignment native arsitektur: sizeof(void*)).
 */
void* arena_alloc(MemoryArena* arena, size_t size) {
    return arena_alloc_align(arena, size, sizeof(void*));
}

/**
 * @brief Mereset seluruh arena secara instan (O(1)).
 */
void arena_reset(MemoryArena* arena) {
    if (arena) {
        arena->offset = 0;
    }
}

/**
 * @brief Membersihkan seluruh alokasi arena dan membebaskan memori ke OS.
 */
void arena_destroy(MemoryArena* arena) {
    if (arena && arena->buffer) {
        free(arena->buffer);
        arena->buffer = NULL;
        arena->capacity = 0;
        arena->offset = 0;
    }
}

// -------------------------------------------------------------
// Driver Program (Pengujian Kasus Nyata)
// -------------------------------------------------------------

typedef struct {
    uint32_t packet_id;
    float    latency;
    uint8_t  payload[6];
} NetworkPacket;

int main(void) {
    MemoryArena arena;
    const size_t ARENA_SIZE = 1024; // 1 KB Arena Buffer

    if (!arena_init(&arena, ARENA_SIZE)) {
        fprintf(stderr, "Gagal mengalokasikan arena memori.\n");
        return 1;
    }

    printf("Arena berhasil dibuat pada basis: %p [Kapasitas: %zu Bytes]\n\n",
           (void*)arena.buffer, arena.capacity);

    // Alokasi 1: Sebuah character tunggal (1 byte)
    char* char_data = (char*)arena_alloc_align(&arena, sizeof(char), 1);
    *char_data = 'X';
    printf("Alloc 1 [char, align 1]       -> Addr: %p | Offset Saat Ini: %zu\n",
           (void*)char_data, arena.offset);

    // Alokasi 2: NetworkPacket Struct (membutuhkan alignment 4 atau 8 byte)
    // Walaupun alokasi sebelumnya 1 byte, pointer berikut akan dilompati (padded)
    // agar beralamat tepat di kelipatan 8 byte.
    NetworkPacket* packet = (NetworkPacket*)arena_alloc_align(&arena, sizeof(NetworkPacket), 8);
    if (!packet) {
        fprintf(stderr, "Alokasi paket gagal!\n");
        return 1;
    }

    packet->packet_id = 9901;
    packet->latency = 0.045f;
    memcpy(packet->payload, "ALGO01", 6);

    printf("Alloc 2 [Struct, align 8]     -> Addr: %p | Offset Saat Ini: %zu\n",
           (void*)packet, arena.offset);
    printf("Padding Terpakai               -> %zu bytes\n",
           (uintptr_t)packet - (uintptr_t)(char_data + 1));
    printf("Verifikasi Alignment struct   -> Alamat modulo 8: %lu\n",
           (uintptr_t)packet % 8);

    // Alokasi 3: Array Data Vektor (misal untuk SIMD, butuh alignment 32 byte)
    float* vector_data = (float*)arena_alloc_align(&arena, 8 * sizeof(float), 32);
    printf("Alloc 3 [AVX Float[8], align 32]-> Addr: %p | Offset Saat Ini: %zu\n",
           (void*)vector_data, arena.offset);
    printf("Verifikasi Alignment AVX      -> Alamat modulo 32: %lu\n",
           (uintptr_t)vector_data % 32);

    // Reset dan Pakai Ulang
    printf("\nMelakukan Arena Reset...\n");
    arena_reset(&arena);
    printf("Offset setelah Reset: %zu. Alokasi baru dapat menimpa buffer tanpa overhead malloc.\n", arena.offset);

    arena_destroy(&arena);
    return 0;
}
