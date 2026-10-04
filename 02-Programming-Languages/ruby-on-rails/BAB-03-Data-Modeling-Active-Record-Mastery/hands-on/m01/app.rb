# app/services/ledger_transaction_service.rb
class LedgerTransactionService
  class InsufficientFundsError < StandardError; end
  class AccountMismatchError < StandardError; end

  def self.transfer(ledger:, source_account:, destination_account:, amount_cents:, reference_id:, description:)
    new(ledger, source_account, destination_account, amount_cents, reference_id, description).execute
  end

  def initialize(ledger, source_account, destination_account, amount_cents, reference_id, description)
    @ledger = ledger
    @source_account = source_account
    @destination_account = destination_account
    @amount_cents = Integer(amount_cents)
    @reference_id = reference_id
    @description = description
  end

  def execute
    raise ArgumentError, "Jumlah transfer harus bernilai positif" if @amount_cents <= 0
    validate_ledger_association!

    # PENCEGAHAN DEADLOCK: Urutkan ID akun saat mengunci baris (Row-Level Locking)
    ordered_account_ids = [@source_account.id, @destination_account.id].sort

    ActiveRecord::Base.transaction(isolation: :serializable) do
      # 1. Pessimistic Locking: SELECT FOR UPDATE berdasarkan ID terurut
      locked_accounts = Account.where(id: ordered_account_ids).order(:id).lock("FOR UPDATE").index_by(&:id)

      locked_source = locked_accounts[@source_account.id]
      locked_dest = locked_accounts[@destination_account.id]

      # 2. Verifikasi Saldo di dalam isolasi transaksi
      if locked_source.balance_cents < @amount_cents
        raise InsufficientFundsError, "Saldo akun #{@source_account.account_number} tidak mencukupi."
      end

      # 3. Mutasi Saldo secara atomik
      locked_source.balance_cents -= @amount_cents
      locked_dest.balance_cents += @amount_cents

      locked_source.save!
      locked_dest.save!

      # 4. Buat Audit Trail Journal Entry (Immutability)
      entry = @ledger.journal_entries.build(
        reference_id: @reference_id,
        description: @description,
        posted_at: Time.current
      )

      # Aturan Akuntansi: Debit mengurangi kredit/mengubah aset, kredit meningkatkan aset
      entry.ledger_lines.build(account: locked_source, amount_cents: -@amount_cents)
      entry.ledger_lines.build(account: locked_dest, amount_cents: @amount_cents)

      entry.save!
      entry
    end
  rescue ActiveRecord::RecordNotUnique
    raise ArgumentError, "Transaksi dengan ID referensi '#{@reference_id}' telah diproses."
  end

  private

  def validate_ledger_association!
    return if @source_account.ledger_id == @ledger.id && @destination_account.ledger_id == @ledger.id

    raise AccountMismatchError, "Akun-akun yang terlibat harus berada di bawah Ledger yang sama."
  end
end
