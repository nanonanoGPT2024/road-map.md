// types/offlineQueue.ts
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface QueuedMutation {
  id: string; // UUIDv4
  endpoint: string;
  method: HttpMethod;
  payload: Record<string, any>;
  headers: Record<string, string>;
  createdAt: number;
  retryCount: number;
  idempotencyKey: string;
}

// services/MutationQueueManager.ts
import { MMKV } from 'react-native-mmkv';
import NetInfo from '@react-native-community/netinfo';

const storage = new MMKV({ id: 'offline-mutation-store' });
const QUEUE_STORAGE_KEY = 'MUTATION_PERSISTENCE_QUEUE';

export class MutationQueueManager {
  private static instance: MutationQueueManager;
  private isProcessing: boolean = false;
  private maxRetries: number = 5;

  private constructor() {}

  public static getInstance(): MutationQueueManager {
    if (!MutationQueueManager.instance) {
      MutationQueueManager.instance = new MutationQueueManager();
    }
    return MutationQueueManager.instance;
  }

  public enqueue(
    mutation: Omit<QueuedMutation, 'id' | 'createdAt' | 'retryCount' | 'idempotencyKey'>
  ): string {
    const queue = this.getQueue();
    const id = this.generateUUID();
    const idempotencyKey = this.generateUUID();

    const newMutation: QueuedMutation = {
      ...mutation,
      id,
      createdAt: Date.now(),
      retryCount: 0,
      idempotencyKey,
    };

    queue.push(newMutation);
    this.persistQueue(queue);
    
    // Trigger pemrosesan jika online
    this.processQueue();
    return id;
  }

  public async processQueue(): Promise<void> {
    if (this.isProcessing) return;

    const isConnected = await this.verifyActiveConnection();
    if (!isConnected) {
      console.warn('[QueueManager] Koneksi tidak tersedia. Antrean ditangguhkan.');
      return;
    }

    this.isProcessing = true;
    const queue = this.getQueue();

    while (queue.length > 0) {
      const currentMutation = queue[0];

      try {
        await this.executeMutation(currentMutation);
        // Mutasi sukses, hapus dari antrean
        queue.shift();
        this.persistQueue(queue);
      } catch (error: any) {
        console.error(`[QueueManager] Gagal memproses mutasi ${currentMutation.id}:`, error);

        if (this.isFatalError(error)) {
          // Kesalahan client 4xx (kecuali 429), buang mutasi untuk mencegah dead-lock antrean
          queue.shift();
          this.persistQueue(queue);
        } else {
          // Kesalahan jaringan / 5xx, terapkan exponential backoff
          currentMutation.retryCount += 1;
          if (currentMutation.retryCount >= this.maxRetries) {
            queue.shift(); // Buang ke Dead-Letter Queue (DLQ)
            this.handleDeadLetter(currentMutation);
          } else {
            this.persistQueue(queue);
            // Hentikan eksekusi batch, tunggu cycle berikutnya
            break;
          }
        }
      }
    }

    this.isProcessing = false;
  }

  private async executeMutation(mutation: QueuedMutation): Promise<Response> {
    const response = await fetch(mutation.endpoint, {
      method: mutation.method,
      headers: {
        'Content-Type': 'application/json',
        'X-Idempotency-Key': mutation.idempotencyKey,
        ...mutation.headers,
      },
      body: JSON.stringify(mutation.payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw { status: response.status, data: errorData };
    }

    return response;
  }

  private async verifyActiveConnection(): Promise<boolean> {
    const netState = await NetInfo.fetch();
    if (!netState.isConnected || !netState.isInternetReachable) {
      return false;
    }

    try {
      // Probing Layer 7 aktif
      const probe = await fetch('https://clients3.google.com/generate_204', {
        method: 'HEAD',
        cache: 'no-store',
      });
      return probe.status === 204;
    } catch {
      return false;
    }
  }

  private isFatalError(error: any): boolean {
    if (error.status && error.status >= 400 && error.status < 500 && error.status !== 429) {
      return true;
    }
    return false;
  }

  private handleDeadLetter(mutation: QueuedMutation): void {
    console.error(`[DLQ] Mutasi dipindahkan ke Dead-Letter Queue: ${mutation.id}`);
    const dlqRaw = storage.getString('MUTATION_DLQ') || '[]';
    const dlq: QueuedMutation[] = JSON.parse(dlqRaw);
    dlq.push(mutation);
    storage.set('MUTATION_DLQ', JSON.stringify(dlq));
  }

  private getQueue(): QueuedMutation[] {
    const data = storage.getString(QUEUE_STORAGE_KEY);
    return data ? JSON.parse(data) : [];
  }

  private persistQueue(queue: QueuedMutation[]): void {
    storage.set(QUEUE_STORAGE_KEY, JSON.stringify(queue));
  }

  private generateUUID(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }
}
