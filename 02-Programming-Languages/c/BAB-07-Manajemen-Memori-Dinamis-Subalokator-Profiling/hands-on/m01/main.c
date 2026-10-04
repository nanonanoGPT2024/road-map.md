#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <time.h>
#include <stdalign.h>

#define MAX_PACKET_PAYLOAD 1536
#define BATCH_SIZE 8
#define TOTAL_BATCHES 5

/* Struktur Metrik Observabilitas */
typedef struct {
    size_t total_allocations;
    size_t total_deallocations;
    size_t current_bytes_used;
    size_t peak_bytes_used;
} MemoryMetrics;

static MemoryMetrics g_metrics = {0};

/* Forward Declaration Helper */
static inline uintptr_t align_forward(uintptr_t ptr, uintptr_t alignment) {
    return (ptr + (alignment - 1)) & ~(alignment - 1);
}

/* --- ARENA SUBALLOCATOR DENGAN PROFILING --- */
typedef struct {
    uint8_t *buffer;
    size_t capacity;
    size_t offset;
} MonitoredArena;

MonitoredArena monitored_arena_create(size_t capacity) {
    MonitoredArena a;
    a.capacity = capacity;
    a.offset = 0;
    a.buffer = (uint8_t *)aligned_alloc(64, capacity); /* Selaras Cache-line 64-byte */
    if (!a.buffer) {
        perror("Alokasi memori buffer arena gagal");
        exit(EXIT_FAILURE);
    }
    return a;
}

void* monitored_arena_alloc(MonitoredArena *arena, size_t size) {
    uintptr_t cur = (uintptr_t)(arena->buffer + arena->offset);
    uintptr_t aligned = align_forward(cur, alignof(max_align_t));
    size_t padding = (size_t)(aligned - cur);
    size_t new_offset = arena->offset + padding + size;

    if (new_offset > arena->capacity) {
        return NULL;
    }

    arena->offset = new_offset;

    /* Update Telemetri */
    g_metrics.total_allocations++;
    g_metrics.current_bytes_used = arena->offset;
    if (g_metrics.current_bytes_used > g_metrics.peak_bytes_used) {
        g_metrics.peak_bytes_used = g_metrics.current_bytes_used;
    }

    return (void *)aligned;
}

void monitored_arena_reset(MonitoredArena *arena) {
    g_metrics.total_deallocations += g_metrics.total_allocations;
    arena->offset = 0;
    g_metrics.current_bytes_used = 0;
}

void monitored_arena_destroy(MonitoredArena *arena) {
    if (arena->buffer) {
        free(arena->buffer);
        arena->buffer = NULL;
    }
}

/* --- REKAYASA SISTEM PAKET JARINGAN --- */
typedef struct {
    uint32_t packet_id;
    uint32_t timestamp;
    size_t   payload_size;
    uint8_t *payload;
} NetworkPacket;

void process_network_packet(NetworkPacket *pkt) {
    /* Simulasi pemrosesan paket (misal: verifikasi checksum payload) */
    uint32_t checksum = 0;
    for (size_t i = 0; i < pkt->payload_size; ++i) {
        checksum ^= pkt->payload[i];
    }
    (void)checksum; // Mengabaikan peringatan variabel tidak digunakan
}

int main(void) {
    printf("=== SIMULASI PEMROSESAN JARINGAN (SUBALOKATOR AKTIF) ===\n");

    /* Buat Arena per-thread berukuran 64 KB */
    MonitoredArena packet_arena = monitored_arena_create(64 * 1024);

    srand((unsigned int)time(NULL));

    for (int batch = 1; batch <= TOTAL_BATCHES; ++batch) {
        printf("\n--- Memproses Batch #%d ---\n", batch);
        
        NetworkPacket packets[BATCH_SIZE];

        /* Tahap Alokasi Batch */
        for (int i = 0; i < BATCH_SIZE; ++i) {
            packets[i].packet_id = (uint32_t)(batch * 100 + i);
            packets[i].timestamp = (uint32_t)time(NULL);
            /* Ukuran payload heterogen acak antara 64 hingga 1500 bita */
            packets[i].payload_size = 64 + (size_t)(rand() % (MAX_PACKET_PAYLOAD - 64));

            packets[i].payload = (uint8_t *)monitored_arena_alloc(&packet_arena, packets[i].payload_size);

            if (!packets[i].payload) {
                fprintf(stderr, "Fatal: Arena kehabisan memori pada batch %d, paket %d!\n", batch, i);
                exit(EXIT_FAILURE);
            }

            /* Inisialisasi payload tiruan */
            memset(packets[i].payload, (uint8_t)(i & 0xFF), packets[i].payload_size);
        }

        /* Tahap Pemrosesan Paket */
        for (int i = 0; i < BATCH_SIZE; ++i) {
            process_network_packet(&packets[i]);
        }

        printf("Batch #%d Selesai. Penggunaan Memori Saat Ini: %zu bita\n", 
               batch, g_metrics.current_bytes_used);

        /* Reset Memori Seketika: Membebaskan seluruh alokasi batch sekaligus dalam O(1) */
        monitored_arena_reset(&packet_arena);
        printf("Arena di-reset. Penggunaan Memori Setelah Reset: %zu bita\n", g_metrics.current_bytes_used);
    }

    printf("\n=== METRIK PROFILING MEMORI FINAL ===\n");
    printf("Total Alokasi Diterbitkan: %zu kali\n", g_metrics.total_allocations);
    printf("Peak Memory (High-Water Mark): %zu bita\n", g_metrics.peak_bytes_used);
    printf("Fragmentasi Eksternal: 0.00%% (Dieliminasi oleh arsitektur Arena)\n");

    monitored_arena_destroy(&packet_arena);
    return 0;
}
