<?php

declare(strict_types=1);

namespace App\Security\Webhook;

use SensitiveParameter;
use InvalidArgumentException;
use RuntimeException;

final class SafeHttpClient
{
    /**
     * Mengambil konten URL publik dengan memvalidasi IP (Anti-SSRF).
     */
    public function secureFetch(string $targetUrl, int $timeoutSeconds = 5): string
    {
        $parts = parse_url($targetUrl);
        if ($parts === false || !isset($parts['scheme'], $parts['host'])) {
            throw new InvalidArgumentException('Malformed URL structure.');
        }

        // 1. Validasi Skema Mutlak: Hanya izinkan HTTPS
        if (strtolower($parts['scheme']) !== 'https') {
            throw new InvalidArgumentException('Insecure protocol: Hanya HTTPS yang diizinkan.');
        }

        $host = $parts['host'];

        // 2. DNS Resolution Manual
        $resolvedIps = dns_get_record($host, DNS_A + DNS_AAAA);
        if (empty($resolvedIps)) {
            throw new RuntimeException("DNS resolution failed for host: {$host}");
        }

        $targetIp = null;
        foreach ($resolvedIps as $record) {
            $candidateIp = $record['ip'] ?? $record['ipv6'] ?? null;
            if ($candidateIp && $this->isPubliclyRoutableIp($candidateIp)) {
                $targetIp = $candidateIp;
                break;
            }
        }

        if ($targetIp === null) {
            throw new RuntimeException('Target host resolve ke jaringan privat atau terlarang.');
        }

        // 3. Eksekusi Request dengan Pinning Target IP via cURL (Anti-DNS Rebinding)
        $port = $parts['port'] ?? 443;
        $ch = curl_init();

        // Parameter CURLOPT_RESOLVE memetakan host:port:ip secara statis
        $resolveMap = ["{$host}:{$port}:{$targetIp}"];

        curl_setopt_array($ch, [
            CURLOPT_URL            => $targetUrl,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => $timeoutSeconds,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_FOLLOWLOCATION => false, // Nonaktifkan redirect otomatis untuk mencegah redirect SSRF bypass
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_RESOLVE        => $resolveMap,
            CURLOPT_PROTOCOLS      => CURLPROTO_HTTPS, // Hanya izinkan protokol HTTPS
        ]);

        $response = curl_exec($ch);
        $error = curl_error($ch);
        $statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($response === false || $statusCode >= 400) {
            throw new RuntimeException("Fetch error: {$error} (HTTP {$statusCode})");
        }

        return (string) $response;
    }

    /**
     * Memeriksa apakah IP publik dan bukan range reserved/internal.
     */
    private function isPubliclyRoutableIp(string $ip): bool
    {
        $filtered = filter_var(
            $ip,
            FILTER_VALIDATE_IP,
            FILTER_FLAG_IPV4 | FILTER_FLAG_IPV6 | 
            FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE
        );

        if ($filtered === false) {
            return false;
        }

        // AWS/Cloud IMDSv2 link-local block eksplisit (169.254.0.0/16)
        if (str_starts_with($ip, '169.254.')) {
            return false;
        }

        return true;
    }
}

final class WebhookSignatureValidator
{
    /**
     * Validasi HMAC SHA-256 Webhook Payload.
     */
    public function validatePayload(
        string $payloadJson,
        string $incomingSignature,
        #[SensitiveParameter] string $secretKey
    ): bool {
        if (empty($incomingSignature) || empty($payloadJson)) {
            return false;
        }

        $calculatedSignature = hash_hmac('sha256', $payloadJson, $secretKey);

        // Constant-time execution memitigasi timing attack
        return hash_equals($calculatedSignature, $incomingSignature);
    }
}

final class PaymentProcessor
{
    public function __construct(
        private readonly \PDO $pdo,
        private readonly SafeHttpClient $httpClient,
        private readonly WebhookSignatureValidator $validator
    ) {}

    /**
     * Pemrosesan transaksi idempotent & race-condition proof.
     */
    public function processWebhook(
        string $rawPayload,
        string $signature,
        #[SensitiveParameter] string $webhookSecret
    ): void {
        // 1. Verifikasi Signature Cryptographic Terlebih Dahulu
        if (!$this->validator->validatePayload($rawPayload, $signature, $webhookSecret)) {
            throw new RuntimeException('Unauthorized webhook signature.');
        }

        // 2. Decode JSON secara ketat
        $data = json_decode($rawPayload, true, 512, JSON_THROW_ON_ERROR);

        $transactionId = $data['transaction_id'] ?? null;
        $receiptUrl = $data['receipt_url'] ?? null;

        if (!$transactionId || !is_string($transactionId)) {
            throw new InvalidArgumentException('Invalid transaction ID.');
        }

        // 3. Database Mutex via Pessimistic Locking dalam Transaksi
        $this->pdo->beginTransaction();

        try {
            $stmt = $this->pdo->prepare(
                'SELECT status, amount FROM transactions WHERE id = :id FOR UPDATE'
            );
            $stmt->execute(['id' => $transactionId]);
            $transaction = $stmt->fetch(\PDO::FETCH_ASSOC);

            if (!$transaction) {
                throw new RuntimeException('Transaction not found.');
            }

            if ($transaction['status'] === 'SETTLED') {
                // Idempotensi: Payload sudah pernah diproses sebelumnya
                $this->pdo->rollBack();
                return;
            }

            // 4. Pengambilan receipt PDF dengan anti-SSRF client jika URL disediakan
            if ($receiptUrl && is_string($receiptUrl)) {
                $receiptContent = $this->httpClient->secureFetch($receiptUrl);
                // Lakukan validasi file content & simpan ke storage terlindungi...
            }

            // 5. Update Status Transaksi
            $updateStmt = $this->pdo->prepare(
                'UPDATE transactions SET status = :status, updated_at = NOW() WHERE id = :id'
            );
            $updateStmt->execute([
                'status' => 'SETTLED',
                'id'     => $transactionId
            ]);

            $this->pdo->commit();
        } catch (\Throwable $e) {
            $this->pdo->rollBack();
            throw $e;
        }
    }
}
