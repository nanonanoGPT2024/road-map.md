<?php

declare(strict_types=1);

namespace Enterprise\PaymentGateway\Provider;

use Enterprise\PaymentGateway\Contract\PaymentGatewayInterface;
use Enterprise\PaymentGateway\Contract\PaymentRequest;
use Enterprise\PaymentGateway\Contract\PaymentResult;
use Enterprise\PaymentGateway\Contract\PaymentStatus;
use Psr\Http\Client\ClientInterface;
use Psr\Http\Message\RequestFactoryInterface;
use Psr\Log\LoggerInterface;
use Psr\Log\NullLogger;
use Throwable;

final class StripePaymentGateway implements PaymentGatewayInterface
{
    private LoggerInterface $logger;

    public function __construct(
        private readonly ClientInterface $httpClient,
        private readonly RequestFactoryInterface $requestFactory,
        private readonly string $apiKey,
        ?LoggerInterface $logger = null
    ) {
        $this->logger = $logger ?? new NullLogger();
    }

    public function setLogger(LoggerInterface $logger): void
    {
        $this->logger = $logger;
    }

    public function process(PaymentRequest $request): PaymentResult
    {
        $this->logger->info("Processing Stripe payment", [
            'transaction_id' => $request->transactionId,
            'amount' => $request->amountInCents,
        ]);

        try {
            $httpRequest = $this->requestFactory->createRequest('POST', 'https://api.stripe.com/v1/charges')
                ->withHeader('Authorization', 'Bearer ' . $this->apiKey)
                ->withHeader('Content-Type', 'application/x-www-form-urlencoded');

            $body = http_build_query([
                'amount' => $request->amountInCents,
                'currency' => strtolower($request->currency),
                'metadata' => array_merge($request->metadata, [
                    'internal_txn_id' => $request->transactionId
                ]),
            ]);

            $httpRequest->getBody()->write($body);

            // Eksekusi HTTP Client berbasis PSR-18
            $httpResponse = $this->httpClient->sendRequest($httpRequest);

            if ($httpResponse->getStatusCode() === 200) {
                $payload = json_decode((string) $httpResponse->getBody(), true, 512, JSON_THROW_ON_ERROR);

                $this->logger->info("Payment successfully settled", [
                    'stripe_charge_id' => $payload['id']
                ]);

                return new PaymentResult(
                    status: PaymentStatus::SUCCESS,
                    providerReferenceId: $payload['id']
                );
            }

            $this->logger->warning("Stripe non-200 transaction", [
                'status_code' => $httpResponse->getStatusCode(),
                'body' => (string) $httpResponse->getBody()
            ]);

            return new PaymentResult(
                status: PaymentStatus::FAILED,
                providerReferenceId: null,
                errorMessage: "HTTP Response code: " . $httpResponse->getStatusCode()
            );

        } catch (Throwable $exception) {
            $this->logger->error("Critical failure during Stripe API dispatch", [
                'error' => $exception->getMessage(),
                'trace' => $exception->getTraceAsString()
            ]);

            return new PaymentResult(
                status: PaymentStatus::FAILED,
                providerReferenceId: null,
                errorMessage: $exception->getMessage()
            );
        }
    }
}
