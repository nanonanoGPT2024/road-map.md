# frozen_string_literal: true

require 'spec_helper'
require 'bigdecimal'
require_relative '../../lib/pay_veloce/payment_processor'
require_relative '../../lib/pay_veloce/fraud_detection_service'

RSpec.describe PayVeloce::PaymentProcessor do
  subject(:processor) { described_class.new(fraud_service: fraud_service) }

  # VERIFIED DOUBLE: Memvalidasi keberadaan method dan arity secara real-time terhadap FraudDetectionService
  let(:fraud_service) { instance_double(PayVeloce::FraudDetectionService) }

  let(:transaction_id) { "tx-99021-x" }
  let(:amount) { BigDecimal("500000.00") }
  let(:currency) { "IDR" }

  describe '#process' do
    context 'ketika nilai transaksi <= 0' do
      let(:amount) { BigDecimal("0.00") }

      it 'melempar error PaymentError dan tidak memanggil fraud service' do
        expect(fraud_service).not_to receive(:evaluate_transaction)

        expect {
          processor.process(transaction_id: transaction_id, amount: amount, currency: currency)
        }.to raise_error(PayVeloce::PaymentError, "Nilai transaksi tidak valid")
      end
    end

    context 'ketika transaksi lolos pengecekan fraud' do
      let(:fraud_result) do
        PayVeloce::FraudEvaluationResult.new(
          flagged: false,
          risk_score: 0.01,
          reason: nil
        )
      end

      before do
        # Verified Double mencegah Mock Drift:
        # Jika signature evaluate_transaction diubah tanpa update test, baris ini melempar MockExpectationError
        allow(fraud_service).to receive(:evaluate_transaction)
          .with(transaction_id: transaction_id, amount: amount, currency: currency)
          .and_return(fraud_result)
      end

      it 'mengembalikan status :settled' do
        status = processor.process(transaction_id: transaction_id, amount: amount, currency: currency)
        expect(status).to eq(:settled)
      end
    end

    context 'ketika transaksi ditandai sebagai fraud' do
      let(:amount) { BigDecimal("25000000.00") }
      let(:fraud_result) do
        PayVeloce::FraudEvaluationResult.new(
          flagged: true,
          risk_score: 0.99,
          reason: "Exceeds daily threshold"
        )
      end

      before do
        allow(fraud_service).to receive(:evaluate_transaction)
          .with(transaction_id: transaction_id, amount: amount, currency: currency)
          .and_return(fraud_result)
      end

      it 'mengembalikan status :rejected' do
        status = processor.process(transaction_id: transaction_id, amount: amount, currency: currency)
        expect(status).to eq(:rejected)
      end
    end
  end
end
