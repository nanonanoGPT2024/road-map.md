# frozen_string_literal: true

require 'rails_helper'

RSpec.describe 'Payments Webhooks Endpoint', type: :request do
  include ActiveJob::TestHelper

  let(:secret_key) { 'test_secret_key_fixed_vector_32bytes' }
  let(:customer_id) { 'cust_998877' }
  let!(:account) { create(:account, external_customer_id: customer_id, balance_cents: 10_000) }

  let(:payload_hash) do
    {
      transaction_id: 'txn_enterprise_001_abc',
      amount_cents: 5_000,
      customer_id: customer_id,
      event_type: 'payment.captured'
    }
  end
  let(:raw_payload) { payload_hash.to_json }
  let(:valid_signature) do
    OpenSSL::HMAC.hexdigest(OpenSSL::Digest.new('sha256'), secret_key, raw_payload)
  end

  before do
    allow(Rails.application.credentials).to receive(:webhook_secret).and_return(secret_key)
  end

  describe 'POST /api/v1/payments/webhooks' do
    let(:headers) do
      {
        'CONTENT_TYPE' => 'application/json',
        'X-Signature-SHA256' => valid_signature
      }
    end

    it 'processes the transaction atomically and enqueues a reconciliation job' do
      expect {
        post '/api/v1/payments/webhooks', params: raw_payload, headers: headers
      }.to change { account.reload.balance_cents }.from(10_000).to(15_000)
       .and change(WebhookEvent, :count).by(1)
       .and have_enqueued_job(ReconciliationJob).with('txn_enterprise_001_abc').on_queue('reconciliation')

      expect(response).to have_http_status(:ok)
      parsed_body = response.parsed_body
      expect(parsed_body).to match(
        'success' => true,
        'duplicate' => false,
        'balance' => 15_000
      )
    end

    context 'when an invalid signature is provided' do
      let(:headers) do
        {
          'CONTENT_TYPE' => 'application/json',
          'X-Signature-SHA256' => 'invalidsignaturehexstringdeadbeef'
        }
      end

      it 'returns a 401 unauthorized status and does not mutate database states' do
        expect {
          post '/api/v1/payments/webhooks', params: raw_payload, headers: headers
        }.to not_change { account.reload.balance_cents }
         .and not_change(WebhookEvent, :count)

        expect(response).to have_http_status(:unauthorized)
        expect(response.parsed_body['error']).to eq('Cryptographic signature mismatch.')
      end
    end

    context 'when identical payload is posted multiple times (Idempotency Test)' do
      it 'safely ignores duplicated deliveries without double-crediting balances' do
        # First execution
        post '/api/v1/payments/webhooks', params: raw_payload, headers: headers
        expect(response).to have_http_status(:ok)
        expect(account.reload.balance_cents).to eq(15_000)

        # Second delivery (duplicate event)
        expect {
          post '/api/v1/payments/webhooks', params: raw_payload, headers: headers
        }.to not_change { account.reload.balance_cents }
         .and not_change(WebhookEvent, :count)

        expect(response).to have_http_status(:ok)
        expect(response.parsed_body['duplicate']).to be(true)
      end
    end
  end
end
