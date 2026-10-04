#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
#include <errno.h>

typedef struct {
    void **buffer;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
    bool shutdown;
    pthread_mutex_t lock;
    pthread_cond_t not_empty;
    pthread_cond_t not_full;
} BoundedQueue;

typedef struct {
    int id;
    int payload_value;
} Message;

// Inisialisasi Queue
BoundedQueue* queue_create(size_t capacity) {
    if (capacity == 0) return NULL;

    BoundedQueue *q = malloc(sizeof(BoundedQueue));
    if (!q) return NULL;

    q->buffer = malloc(sizeof(void*) * capacity);
    if (!q->buffer) {
        free(q);
        return NULL;
    }

    q->capacity = capacity;
    q->head = 0;
    q->tail = 0;
    q->count = 0;
    q->shutdown = false;

    pthread_mutex_init(&q->lock, NULL);
    pthread_cond_init(&q->not_empty, NULL);
    pthread_cond_init(&q->not_full, NULL);

    return q;
}

// Push item (Producer)
bool queue_push(BoundedQueue *q, void *item) {
    pthread_mutex_lock(&q->lock);

    // Evaluasi loop untuk menangani spurious wakeup dan kapasitas
    while (q->count == q->capacity && !q->shutdown) {
        pthread_cond_wait(&q->not_full, &q->lock);
    }

    if (q->shutdown) {
        pthread_mutex_unlock(&q->lock);
        return false;
    }

    q->buffer[q->tail] = item;
    q->tail = (q->tail + 1) % q->capacity;
    q->count++;

    // Beritahukan konsumen bahwa data tersedia
    pthread_cond_signal(&q->not_empty);

    pthread_mutex_unlock(&q->lock);
    return true;
}

// Pop item (Consumer)
bool queue_pop(BoundedQueue *q, void **item) {
    pthread_mutex_lock(&q->lock);

    while (q->count == 0 && !q->shutdown) {
        pthread_cond_wait(&q->not_empty, &q->lock);
    }

    if (q->count == 0 && q->shutdown) {
        pthread_mutex_unlock(&q->lock);
        return false;
    }

    *item = q->buffer[q->head];
    q->head = (q->head + 1) % q->capacity;
    q->count--;

    // Beritahukan produsen bahwa slot telah kosong
    pthread_cond_signal(&q->not_full);

    pthread_mutex_unlock(&q->lock);
    return true;
}

// Menghentikan Queue dan membangunkan semua thread
void queue_shutdown(BoundedQueue *q) {
    pthread_mutex_lock(&q->lock);
    q->shutdown = true;
    pthread_cond_broadcast(&q->not_empty);
    pthread_cond_broadcast(&q->not_full);
    pthread_mutex_unlock(&q->lock);
}

// Dealokasi Queue
void queue_destroy(BoundedQueue *q) {
    if (!q) return;
    pthread_mutex_destroy(&q->lock);
    pthread_cond_destroy(&q->not_empty);
    pthread_cond_destroy(&q->not_full);
    free(q->buffer);
    free(q);
}

/* ================= SIMULASI MULTI-THREADING ================= */

#define NUM_PRODUCERS 2
#define NUM_CONSUMERS 4
#define ITEMS_PER_PRODUCER 20

static atomic_int g_items_produced = ATOMIC_VAR_INIT(0);
static atomic_int g_items_consumed = ATOMIC_VAR_INIT(0);

void* producer_worker(void *arg) {
    BoundedQueue *q = (BoundedQueue*)arg;
    
    for (int i = 0; i < ITEMS_PER_PRODUCER; ++i) {
        Message *msg = malloc(sizeof(Message));
        msg->id = atomic_fetch_add(&g_items_produced, 1);
        msg->payload_value = rand() % 1000;

        if (!queue_push(q, msg)) {
            // Jika shutdown dipanggil sebelum selesai
            free(msg);
            break;
        }
        usleep(10000); // Simulasi kerja I/O 10ms
    }
    return NULL;
}

void* consumer_worker(void *arg) {
    BoundedQueue *q = (BoundedQueue*)arg;
    void *raw_item = NULL;

    while (queue_pop(q, &raw_item)) {
        Message *msg = (Message*)raw_item;
        atomic_fetch_add(&g_items_consumed, 1);
        printf("[Consumer %lu] Memproses Pesan ID: %02d (Val: %d)\n", 
               (unsigned long)pthread_self(), msg->id, msg->payload_value);
        free(msg);
        usleep(25000); // Simulasi pemrosesan 25ms
    }
    return NULL;
}

int main(void) {
    srand(42);
    BoundedQueue *q = queue_create(5); // Kapasitas kecil untuk memaksa blocking

    pthread_t producers[NUM_PRODUCERS];
    pthread_t consumers[NUM_CONSUMERS];

    printf("Menginisialisasi sistem: %d Produsen, %d Konsumen, Kapasitas Antrean: 5\n\n",
           NUM_PRODUCERS, NUM_CONSUMERS);

    for (int i = 0; i < NUM_CONSUMERS; ++i) {
        pthread_create(&consumers[i], NULL, consumer_worker, q);
    }
    for (int i = 0; i < NUM_PRODUCERS; ++i) {
        pthread_create(&producers[i], NULL, producer_worker, q);
    }

    // Tunggu semua produsen selesai memproduksi pesan
    for (int i = 0; i < NUM_PRODUCERS; ++i) {
        pthread_join(producers[i], NULL);
    }
    printf("\n--> Semua produsen selesai. Mematikan sistem antrean...\n");

    // Lakukan graceful shutdown dan tunggu antrean terkuras
    queue_shutdown(q);

    // Tunggu semua konsumen memproses sisa data dan berhenti
    for (int i = 0; i < NUM_CONSUMERS; ++i) {
        pthread_join(consumers[i], NULL);
    }

    printf("\n=== STATISTIK EKSEKUSI ===\n");
    printf("Total Item Diproduksi: %d\n", atomic_load(&g_items_produced));
    printf("Total Item Dikonsumsi: %d\n", atomic_load(&g_items_consumed));

    queue_destroy(q);
    printf("Semua sumber daya memori dan primitif POSIX berhasil dibebaskan.\n");

    return EXIT_SUCCESS;
}
