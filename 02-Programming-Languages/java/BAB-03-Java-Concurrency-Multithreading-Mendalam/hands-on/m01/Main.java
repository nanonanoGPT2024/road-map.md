package com.architect.concurrency.ratelimiter;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.StampedLock;

public final class DistributedScaleRateLimiter {

    private final int maxRequestsPerWindow;
    private final long windowSizeNanos;
    private final ConcurrentHashMap<String, SlidingWindowBucket> merchantBuckets;
    private final ScheduledExecutorService cleanupScheduler;

    public DistributedScaleRateLimiter(int maxRequestsPerWindow, long windowSize, TimeUnit timeUnit) {
        if (maxRequestsPerWindow <= 0) {
            throw new IllegalArgumentException("Max requests harus lebih besar dari 0");
        }
        this.maxRequestsPerWindow = maxRequestsPerWindow;
        this.windowSizeNanos = timeUnit.toNanos(windowSize);
        this.merchantBuckets = new ConcurrentHashMap<>();
        
        // Background thread pembersih untuk mencegah memori membengkak tak terbatas
        this.cleanupScheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "RateLimiter-Cleaner");
            t.setDaemon(true);
            return t;
        });
        this.cleanupScheduler.scheduleAtFixedRate(this::evictStaleBuckets, 1, 1, TimeUnit.MINUTES);
    }

    public boolean tryAcquire(String merchantApiKey) {
        Objects.requireNonNull(merchantApiKey, "merchantApiKey tidak boleh bernilai null");
        long currentNanos = System.nanoTime();

        SlidingWindowBucket bucket = merchantBuckets.computeIfAbsent(
                merchantApiKey, 
                k -> new SlidingWindowBucket()
        );

        return bucket.tryConsume(currentNanos, windowSizeNanos, maxRequestsPerWindow);
    }

    private void evictStaleBuckets() {
        long currentNanos = System.nanoTime();
        merchantBuckets.forEach((key, bucket) -> {
            if (bucket.isInactive(currentNanos, windowSizeNanos)) {
                merchantBuckets.remove(key, bucket);
            }
        });
    }

    public void shutdown() {
        cleanupScheduler.shutdown();
    }

    /**
     * Bucket internal berkinerja tinggi yang diamankan via StampedLock
     */
    private static final class SlidingWindowBucket {
        private final Deque<Long> timestampDeque = new ArrayDeque<>();
        private final StampedLock lock = new StampedLock();
        private long lastAccessNanos = System.nanoTime();

        public boolean tryConsume(long currentNanos, long windowSizeNanos, int maxAllowed) {
            long boundaryNanos = currentNanos - windowSizeNanos;

            // 1. Optimistic Reading Phase (Non-blocking check)
            long stamp = lock.tryOptimisticRead();
            boolean needExclusiveLock = false;

            if (stamp != 0L) {
                // Membaca status snapshot
                int currentSize = timestampDeque.size();
                long oldestTimestamp = currentSize > 0 ? timestampDeque.peekFirst() : 0L;

                if (lock.validate(stamp)) {
                    // Validasi berhasil: tidak ada penulisan konkuren selama pembacaan di atas
                    if (currentSize >= maxAllowed && oldestTimestamp > boundaryNanos) {
                        // Kuota penuh secara optimis terbukti valid, tolak request seketika
                        return false;
                    }
                }
            }

            // 2. Fallback ke Pessimistic Write Lock
            long writeStamp = lock.writeLock();
            try {
                this.lastAccessNanos = currentNanos;

                // Eviksi timestamp kadaluarsa dari sliding window
                while (!timestampDeque.isEmpty() && timestampDeque.peekFirst() <= boundaryNanos) {
                    timestampDeque.pollFirst();
                }

                if (timestampDeque.size() < maxAllowed) {
                    timestampDeque.addLast(currentNanos);
                    return true;
                } else {
                    return false;
                }
            } finally {
                lock.unlockWrite(writeStamp);
            }
        }

        public boolean isInactive(long currentNanos, long windowSizeNanos) {
            long stamp = lock.readLock();
            try {
                return (currentNanos - lastAccessNanos) > (windowSizeNanos * 2);
            } finally {
                lock.unlockRead(stamp);
            }
        }
    }
}
