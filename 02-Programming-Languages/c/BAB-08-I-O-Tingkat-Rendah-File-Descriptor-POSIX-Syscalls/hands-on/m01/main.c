/**
 * wal_engine.c - Production-Grade Minimal Write-Ahead Logger
 * Target: POSIX Compliant Operating Systems (Linux, BSD, macOS)
 */

#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>

#define WAL_MAGIC 0x57414C31 /* ASCII: "WAL1" */

#pragma pack(push, 1)
typedef struct {
    uint32_t magic;       /* WAL Identifier */
    uint64_t seq_id;      /* Sequence ID Transaksi */
    uint32_t payload_len; /* Ukuran data muatan */
    uint32_t crc32;       /* Checksum payload untuk integritas */
} wal_frame_header_t;
#pragma pack(pop)

/* Implementasi Sederhana Standar IEEE 802.3 CRC32 */
static uint32_t calculate_crc32(const uint8_t *data, size_t length) {
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (int j = 0; j < 8; ++j) {
            crc = (crc >> 1) ^ (0xEDB88320 & (-(crc & 1)));
        }
    }
    return ~crc;
}

typedef struct {
    int fd;
    uint64_t current_seq;
} wal_logger_t;

/* Inisialisasi atau Pembukaan Berkas WAL */
wal_logger_t *wal_open(const char *path) {
    if (!path) {
        return NULL;
    }

    wal_logger_t *logger = malloc(sizeof(wal_logger_t));
    if (!logger) {
        return NULL;
    }

    /* O_APPEND memastikan penulisan selalu berada di ujung berkas di level kernel */
    int flags = O_RDWR | O_CREAT | O_APPEND | O_CLOEXEC;
    mode_t mode = 0600; /* Proteksi keamanan: Hanya pemilik yang dapat R/W */
    
    logger->fd = open(path, flags, mode);
    if (logger->fd < 0) {
        free(logger);
        return NULL;
    }

    /* Validasi & Deteksi Urutan ID Terakhir untuk Sinkronisasi State */
    struct stat st;
    if (fstat(logger->fd, &st) < 0) {
        close(logger->fd);
        free(logger);
        return NULL;
    }

    logger->current_seq = 0;

    /* Scan berkas jika berkas sudah eksis dan berisi log lama */
    if (st.st_size > 0) {
        off_t offset = 0;
        wal_frame_header_t header;

        while (offset < st.st_size) {
            ssize_t bytes = pread(logger->fd, &header, sizeof(wal_frame_header_t), offset);
            if (bytes != (ssize_t)sizeof(wal_frame_header_t)) {
                break; /* Record rusak/terpotong di ujung berkas */
            }

            if (header.magic != WAL_MAGIC) {
                break; /* Header korup terdeteksi */
            }

            logger->current_seq = header.seq_id;
            offset += sizeof(wal_frame_header_t) + header.payload_len;
        }
    }

    return logger;
}

/* Penulisan Transaksi Atomik Ter-Frame */
bool wal_append(wal_logger_t *logger, const void *payload, uint32_t payload_len) {
    if (!logger || !payload || payload_len == 0) {
        return false;
    }

    wal_frame_header_t header;
    header.magic = WAL_MAGIC;
    header.seq_id = ++logger->current_seq;
    header.payload_len = payload_len;
    header.crc32 = calculate_crc32((const uint8_t *)payload, payload_len);

    /* Susun seluruh frame ke dalam contiguous user buffer untuk meminimalkan I/O calls */
    size_t total_frame_size = sizeof(wal_frame_header_t) + payload_len;
    uint8_t *frame_buffer = malloc(total_frame_size);
    if (!frame_buffer) {
        --logger->current_seq;
        return false;
    }

    memcpy(frame_buffer, &header, sizeof(wal_frame_header_t));
    memcpy(frame_buffer + sizeof(wal_frame_header_t), payload, payload_len);

    /* Tulis frame secara deterministik */
    uint8_t *write_ptr = frame_buffer;
    size_t bytes_to_write = total_frame_size;

    while (bytes_to_write > 0) {
        ssize_t written = write(logger->fd, write_ptr, bytes_to_write);
        if (written < 0) {
            if (errno == EINTR) {
                continue;
            }
            free(frame_buffer);
            --logger->current_seq;
            return false;
        }
        bytes_to_write -= (size_t)written;
        write_ptr += written;
    }

    free(frame_buffer);

    /* 
     * fdatasync: Memaksa kernel dan controller disk untuk melakukan flush 
     * page buffer payload ini ke media non-volatile fisik.
     */
    if (fdatasync(logger->fd) < 0) {
        return false;
    }

    return true;
}

/* Menutup WAL Logger */
void wal_close(wal_logger_t *logger) {
    if (!logger) return;
    if (logger->fd >= 0) {
        fdatasync(logger->fd);
        close(logger->fd);
    }
    free(logger);
}

int main(void) {
    const char *wal_path = "transaction_ledger.wal";
    printf("Menginisialisasi WAL Engine pada: %s\n", wal_path);

    wal_logger_t *logger = wal_open(wal_path);
    if (!logger) {
        perror("Inisialisasi WAL gagal");
        return EXIT_FAILURE;
    }

    printf("Seq ID Terakhir dari penyimpanan: %lu\n", (unsigned long)logger->current_seq);

    /* Simulasi Transaksi Finansial Tingkat Tinggi */
    const char *tx1 = "TXID=1001;SENDER=ALICE;RECV=BOB;AMOUNT=5000.00";
    const char *tx2 = "TXID=1002;SENDER=CHARLIE;RECV=DAVE;AMOUNT=125.50";

    if (wal_append(logger, tx1, (uint32_t)strlen(tx1))) {
        printf("Transaksi 1 berhasil dipersistensikan secara sinkron.\n");
    } else {
        fprintf(stderr, "Gagal menulis Transaksi 1!\n");
    }

    if (wal_append(logger, tx2, (uint32_t)strlen(tx2))) {
        printf("Transaksi 2 berhasil dipersistensikan secara sinkron.\n");
    } else {
        fprintf(stderr, "Gagal menulis Transaksi 2!\n");
    }

    wal_close(logger);
    printf("WAL Engine ditutup secara aman.\n");
    return EXIT_SUCCESS;
}
