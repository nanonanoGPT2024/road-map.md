<?php

declare(strict_types=1);

namespace Core\Application\Service;

use Core\Application\Port\In\RenewSubscriptionUseCaseInterface;
use Core\Application\Port\Out\SubscriptionRepositoryPort;
use Core\Application\Port\Out\PaymentGatewayPort;
use Core\Application\Port\Out\NotificationEventPort;
use Core\Application\DTO\RenewSubscriptionCommand;
use Core\Application\DTO\RenewSubscriptionResponse;
use Core\Domain\Model\SubscriptionId;
use DateTimeImmutable;
use Exception;

final readonly class RenewSubscriptionService implements RenewSubscriptionUseCaseInterface
{
    public function __construct(
        private SubscriptionRepositoryPort $repository,
        private PaymentGatewayPort $paymentGateway,
        private NotificationEventPort $notifier
    ) {}

    public function execute(RenewSubscriptionCommand $command): RenewSubscriptionResponse
    {
        $id = new SubscriptionId($command->subscriptionId);
        $subscription = $this->repository->findById($id);

        if (!$subscription) {
            return new RenewSubscriptionResponse($command->subscriptionId, false, "Subscription not found");
        }

        $now = new DateTimeImmutable();
        $idempotencyKey = sprintf("sub_%s_%s", $subscription->getId()->value, $now->format('Ym'));

        try {
            // Eksekusi I/O ke Payment Provider melalui Driven Port
            $this->paymentGateway->charge(
                $subscription->getCustomerId(),
                $subscription->getRenewalAmountInCents(),
                $idempotencyKey
            );

            // Mutasi status domain secara murni
            $subscription->renewSuccessfully($now);

            // Persistensi perubahan
            $this->repository->save($subscription);

            // Notifikasi asinkron/sinkron via Port
            $this->notifier->notifySubscriptionRenewed($subscription->getCustomerId(), $subscription->getExpiresAt());

            return new RenewSubscriptionResponse($subscription->getId()->value, true, "Renewal successful");
        } catch (Exception $e) {
            // Tangani kegagalan: Update model ke status PAST_DUE
            $subscription->markAsPaymentFailed();
            $this->repository->save($subscription);

            $this->notifier->notifyPaymentFailed($subscription->getCustomerId(), $e->getMessage());

            return new RenewSubscriptionResponse(
                $subscription->getId()->value, 
                false, 
                "Payment failed: " . $e->getMessage()
            );
        }
    }
}
