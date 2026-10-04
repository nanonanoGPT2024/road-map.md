// ==========================================
// FILE: com/payment/domain/PaymentModels.java
// ==========================================
package com.payment.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

// --- Value Objects ---
public final class PaymentModels {
    private PaymentModels() {}

    public record TransactionId(UUID value) {
        public TransactionId {
            Objects.requireNonNull(value, "TransactionId cannot be null");
        }
        public static TransactionId generate() {
            return new TransactionId(UUID.randomUUID());
        }
    }

    public record Money(BigDecimal amount, String currency) {
        public Money {
            Objects.requireNonNull(amount, "Amount cannot be null");
            Objects.requireNonNull(currency, "Currency cannot be null");
            if (amount.scale() > 2) {
                amount = amount.setScale(2, RoundingMode.HALF_EVEN);
            }
        }

        public static Money of(String amount, String currency) {
            return new Money(new BigDecimal(amount), currency);
        }

        public Money applyFeePercentage(BigDecimal percentage) {
            BigDecimal feeAmount = this.amount.multiply(percentage)
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_EVEN);
            return new Money(feeAmount, this.currency);
        }

        public Money subtract(Money other) {
            if (!this.currency.equals(other.currency)) {
                throw new IllegalArgumentException("Mismatched currency");
            }
            return new Money(this.amount.subtract(other.amount), this.currency);
        }
    }

    // --- Domain Events ---
    public sealed interface PaymentEvent {
        TransactionId transactionId();
        Instant occurredAt();

        record PaymentAuthorized(TransactionId transactionId, Money amount, Instant occurredAt) implements PaymentEvent {}
        record PaymentCaptured(TransactionId transactionId, Money netAmount, Money feeApplied, Instant occurredAt) implements PaymentEvent {}
        record PaymentVoided(TransactionId transactionId, String reason, Instant occurredAt) implements PaymentEvent {}
    }

    // --- Algebraic State Machine (Sum Types) ---
    public sealed interface PaymentState {
        record Authorized(Money grossAmount, Instant authorizedAt) implements PaymentState {}
        record Captured(Money grossAmount, Money fee, Money netAmount, Instant capturedAt) implements PaymentState {}
        record Voided(String reason, Instant voidedAt) implements PaymentState {}
    }

    // --- Domain Error Representations ---
    public sealed interface SettlementError {
        record InvalidStateTransition(String message) implements SettlementError {}
        record CurrencyMismatch(String expected, String actual) implements SettlementError {}
        record ExcessiveFee(String message) implements SettlementError {}
    }

    // --- Functional Entity Container ---
    public record PaymentAggregate(
            TransactionId id,
            PaymentState state,
            long version
    ) {
        public PaymentAggregate {
            Objects.requireNonNull(id);
            Objects.requireNonNull(state);
        }

        // Pure factory method
        public static PaymentAggregate initialize(TransactionId id, Money amount, Instant timestamp) {
            return new PaymentAggregate(id, new PaymentState.Authorized(amount, timestamp), 1L);
        }

        // Pure State Transition: Mengembalikan state baru beserta Domain Event
        public DomainResult<TransitionResult, SettlementError> capture(BigDecimal feePercentage, Instant timestamp) {
            return switch (this.state) {
                case PaymentState.Authorized auth -> {
                    if (feePercentage.compareTo(BigDecimal.valueOf(50)) > 0) {
                        yield DomainResult.failure(new SettlementError.ExcessiveFee("Fee cannot exceed 50%"));
                    }
                    Money fee = auth.grossAmount().applyFeePercentage(feePercentage);
                    Money net = auth.grossAmount().subtract(fee);

                    PaymentState newState = new PaymentState.Captured(auth.grossAmount(), fee, net, timestamp);
                    PaymentAggregate newAggregate = new PaymentAggregate(this.id, newState, this.version + 1);
                    PaymentEvent event = new PaymentEvent.PaymentCaptured(this.id, net, fee, timestamp);

                    yield DomainResult.success(new TransitionResult(newAggregate, List.of(event)));
                }
                case PaymentState.Captured c ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Transaction already captured at " + c.capturedAt()));
                case PaymentState.Voided v ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Cannot capture voided transaction: " + v.reason()));
            };
        }

        public DomainResult<TransitionResult, SettlementError> voidTransaction(String reason, Instant timestamp) {
            return switch (this.state) {
                case PaymentState.Authorized auth -> {
                    PaymentState newState = new PaymentState.Voided(reason, timestamp);
                    PaymentAggregate newAggregate = new PaymentAggregate(this.id, newState, this.version + 1);
                    PaymentEvent event = new PaymentEvent.PaymentVoided(this.id, reason, timestamp);
                    yield DomainResult.success(new TransitionResult(newAggregate, List.of(event)));
                }
                case PaymentState.Captured c ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Cannot void an already captured transaction"));
                case PaymentState.Voided v ->
                    DomainResult.failure(new SettlementError.InvalidStateTransition("Transaction is already voided"));
            };
        }
    }

    public record TransitionResult(PaymentAggregate aggregate, List<PaymentEvent> events) {}
}
