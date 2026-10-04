# frozen_string_literal: true

require 'dry/monads'
require 'dry/monads/do'
require 'json'
require 'securerandom'
require 'bigdecimal'

# ==============================================================================
# 1. INFRASTRUCTURE SIMULATION (Database Schema & Connection Adapter)
# ==============================================================================
module Infrastructure
  # Mock Storage Engine Thread-Safe dengan Pessimistic Locking
  class DatabaseEngine
    def initialize
      @storage = {
        accounts: {},
        ledger_entries: {},
        outbox_events: {},
        idempotency_keys: {}
      }
      @mutex = Mutex.new
      @row_locks = Hash.new { |h, k| h[k] = Mutex.new }
    end

    def transaction
      @mutex.synchronize do
        # Simulasi Transaction isolation boundary
        yield self
      end
    end

    def acquire_row_lock(table, id)
      # Mengunci baris spesifik untuk mitigasi Lost Update
      lock = @mutex.synchronize { @row_locks["#{table}:#{id}"] }
      lock.lock
      # Pastikan dilepas oleh framework transaction lifecycle
      at_exit { lock.unlock if lock.locked? }
    end

    def release_row_lock(table, id)
      lock = @mutex.synchronize { @row_locks["#{table}:#{id}"] }
      lock.unlock if lock.locked?
    end

    attr_reader :storage
  end
end

# ==============================================================================
# 2. DOMAIN MODEL & VALUE OBJECTS
# ==============================================================================
module Domain
  class InsufficientFundsError < StandardError; end

  class LedgerAmount
    attr_reader :cents, :currency

    def initialize(cents:, currency: 'IDR')
      @cents = Integer(cents)
      @currency = currency.to_s.upcase.freeze
      raise ArgumentError, "Amount must be positive" if @cents < 0
      freeze
    end

    def +(other)
      assert_currency!(other)
      LedgerAmount.new(cents: @cents + other.cents, currency: @currency)
    end

    def -(other)
      assert_currency!(other)
      raise InsufficientFundsError, "Insufficient funds" if @cents < other.cents
      LedgerAmount.new(cents: @cents - other.cents, currency: @currency)
    end

    private

    def assert_currency!(other)
      raise ArgumentError, "Currency mismatch" unless @currency == other.currency
    end
  end

  class Account
    attr_reader :id, :balance, :version

    def initialize(id:, balance:, version: 0)
      @id = id
      @balance = balance
      @version = version
    end

    def debit!(amount)
      @balance = @balance - amount
      @version += 1
      self
    end

    def credit!(amount)
      @balance = @balance + amount
      @version += 1
      self
    end
  end

  class LedgerEntry
    attr_reader :id, :source_account_id, :target_account_id, :amount_cents, :currency, :created_at

    def initialize(id:, source_account_id:, target_account_id:, amount_cents:, currency:, created_at: Time.now.utc)
      @id = id
      @source_account_id = source_account_id
      @target_account_id = target_account_id
      @amount_cents = amount_cents
      @currency = currency
      @created_at = created_at
      freeze
    end
  end
end

# ==============================================================================
# 3. SECONDARY ADAPTERS (Repositories & Outbox)
# ==============================================================================
module Adapters
  class PostgresLedgerRepository
    def initialize(db)
      @db = db
    end

    def find_account_for_update(account_id)
      @db.acquire_row_lock(:accounts, account_id)
      data = @db.storage[:accounts][account_id]
      return nil unless data

      Domain::Account.new(
        id: data[:id],
        balance: Domain::LedgerAmount.new(cents: data[:balance_cents], currency: data[:currency]),
        version: data[:version]
      )
    end

    def save_account(account)
      @db.storage[:accounts][account.id] = {
        id: account.id,
        balance_cents: account.balance.cents,
        currency: account.balance.currency,
        version: account.version
      }
      @db.release_row_lock(:accounts, account.id)
    end

    def create_ledger_entry(entry)
      @db.storage[:ledger_entries][entry.id] = {
        id: entry.id,
        source_account_id: entry.source_account_id,
        target_account_id: entry.target_account_id,
        amount_cents: entry.amount_cents,
        currency: entry.currency,
        created_at: entry.created_at
      }
    end
  end

  class PostgresOutboxRepository
    def initialize(db)
      @db = db
    end

    def persist_event(event_type:, aggregate_type:, aggregate_id:, payload:)
      event_id = SecureRandom.uuid
      @db.storage[:outbox_events][event_id] = {
        id: event_id,
        event_type: event_type,
        aggregate_type: aggregate_type,
        aggregate_id: aggregate_id,
        payload: payload.to_json,
        status: :pending,
        created_at: Time.now.utc
      }
    end
  end

  class IdempotencyAdapter
    def initialize(db)
      @db = db
    end

    def register_key(key)
      if @db.storage[:idempotency_keys].key?(key)
        return false
      end
      @db.storage[:idempotency_keys][key] = { locked_at: Time.now.utc }
      true
    end
  end
end

# ==============================================================================
# 4. APPLICATION CORE / USE CASE (Command Orchestration)
# ==============================================================================
module UseCases
  class TransferFundsCommand
    include Dry::Monads[:result]
    include Dry::Monads::Do.for(:call)

    def initialize(db:, ledger_repo:, outbox_repo:, idempotency:)
      @db = db
      @ledger_repo = ledger_repo
      @outbox_repo = outbox_repo
      @idempotency = idempotency
    end

    def call(idempotency_key:, source_id:, target_id:, amount_cents:, currency:)
      # 1. Validasi Idempotensi
      yield assert_idempotency(idempotency_key)

      # 2. Validasi Domain Rules Parameter
      transfer_amount = yield instantiate_amount(amount_cents, currency)

      # 3. Eksekusi Unit of Work Atomik
      result = @db.transaction do
        # 3.1 Lock and Fetch Source Account
        source_acc = yield fetch_account(source_id)
        # 3.2 Lock and Fetch Target Account
        target_acc = yield fetch_account(target_id)

        # 3.3 Eksekusi Mutasi Invarian Domain
        yield apply_transfer(source_acc, target_acc, transfer_amount)

        # 3.4 Simpan Perubahan Domain (State Mutasi)
        @ledger_repo.save_account(source_acc)
        @ledger_repo.save_account(target_acc)

        # 3.5 Buat Immutable Audit Record
        entry = Domain::LedgerEntry.new(
          id: SecureRandom.uuid,
          source_account_id: source_acc.id,
          target_account_id: target_acc.id,
          amount_cents: transfer_amount.cents,
          currency: transfer_amount.currency
        )
        @ledger_repo.create_ledger_entry(entry)

        # 3.6 Tulis ke Transactional Outbox (Atomic Dual-Write Prevention)
        @outbox_repo.persist_event(
          event_type: 'LedgerTransferCompleted',
          aggregate_type: 'BankAccount',
          aggregate_id: source_acc.id,
          payload: {
            ledger_entry_id: entry.id,
            source_id: source_acc.id,
            target_id: target_acc.id,
            amount: transfer_amount.cents,
            currency: transfer_amount.currency
          }
        )

        Success(entry)
      end

      result
    end

    private

    def assert_idempotency(key)
      return Success() if @idempotency.register_key(key)
      Failure([:conflict, "Idempotency key collision. Operation already processed or in-flight."])
    end

    def instantiate_amount(cents, currency)
      Success(Domain::LedgerAmount.new(cents: cents, currency: currency))
    rescue ArgumentError => e
      Failure([:unprocessable_entity, e.message])
    end

    def fetch_account(account_id)
      account = @ledger_repo.find_account_for_update(account_id)
      return Failure([:not_found, "Account #{account_id} not found."]) unless account
      Success(account)
    end

    def apply_transfer(source, target, amount)
      source.debit!(amount)
      target.credit!(amount)
      Success()
    rescue Domain::InsufficientFundsError => e
      Failure([:unprocessable_entity, e.message])
    rescue StandardError => e
      Failure([:domain_error, e.message])
    end
  end
end

# ==============================================================================
# 5. INTEGRATION VERIFICATION RUNNER
# ==============================================================================

# Inisialisasi Environment
db = Infrastructure::DatabaseEngine.new
ledger_repo = Adapters::PostgresLedgerRepository.new(db)
outbox_repo = Adapters::PostgresOutboxRepository.new(db)
idempotency = Adapters::IdempotencyAdapter.new(db)

# Seed Data Rekening
db.storage[:accounts]['acc-source-1'] = { id: 'acc-source-1', balance_cents: 500_000, currency: 'IDR', version: 1 }
db.storage[:accounts]['acc-target-2'] = { id: 'acc-target-2', balance_cents: 100_000, currency: 'IDR', version: 1 }

use_case = UseCases::TransferFundsCommand.new(
  db: db,
  ledger_repo: ledger_repo,
  outbox_repo: outbox_repo,
  idempotency: idempotency
)

puts "=== SKENARIO 1: Sukses Transfer Antar Rekening ==="
result = use_case.call(
  idempotency_key: 'tx-uuid-0001',
  source_id: 'acc-source-1',
  target_id: 'acc-target-2',
  amount_cents: 250_000,
  currency: 'IDR'
)

if result.success?
  entry = result.value!
  puts "Status: SUCCESS"
  puts "Ledger Entry ID: #{entry.id}"
  puts "Saldo Pengirim : #{db.storage[:accounts]['acc-source-1'][:balance_cents]} IDR"
  puts "Saldo Penerima : #{db.storage[:accounts]['acc-target-2'][:balance_cents]} IDR"
  puts "Tabel Outbox Event: #{db.storage[:outbox_events].values.last[:payload]}"
else
  puts "Status: FAILED, Reason: #{result.failure}"
end

puts "\n=== SKENARIO 2: Deteksi Idempotensi Ganda (Replay Attack) ==="
replay_result = use_case.call(
  idempotency_key: 'tx-uuid-0001', # Menggunakan key yang sama
  source_id: 'acc-source-1',
  target_id: 'acc-target-2',
  amount_cents: 250_000,
  currency: 'IDR'
)
puts "Status Replay: #{replay_result.failure? ? 'REJECTED (Expected)' : 'PASSED (Bug)'}"
puts "Error Details: #{replay_result.failure.inspect}"

puts "\n=== SKENARIO 3: Kegagalan Invarian Saldo Tidak Cukup ==="
insufficient_result = use_case.call(
  idempotency_key: 'tx-uuid-0002',
  source_id: 'acc-source-1',
  target_id: 'acc-target-2',
  amount_cents: 999_999_999, # Melebihi saldo sisa (250_000)
  currency: 'IDR'
)
puts "Status Overdraft: #{insufficient_result.failure? ? 'REJECTED (Expected)' : 'PASSED (Bug)'}"
puts "Error Details: #{insufficient_result.failure.inspect}"
