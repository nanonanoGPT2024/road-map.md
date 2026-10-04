package com.scaladev.ledger

import scala.annotation.tailrec

// 1. DOMAIN MODELS (Immutable Case Classes & Sealed Types)
enum TransactionType:
  case Credit, Debit

case class Transaction(
    id: String,
    accountId: String,
    amount: BigDecimal,
    txType: TransactionType
)

case class AccountState(
    accountId: String,
    balance: BigDecimal,
    successfulTxCount: Int,
    failedTxCount: Int
)

enum TransactionResult:
  case Success(newState: AccountState, txId: String)
  case Rejected(currentState: AccountState, txId: String, reason: String)

case class LedgerReport(
    finalState: AccountState,
    rejectedTransactions: List[(String, String)] // Tuple: (TxId, Reason)
)

// 2. ENGINE LOGIC (Pure FP Engine)
object TransactionEngine:

  /**
   * Fungsi transisi status murni (State Transition Function)
   * f(State, Event) => State
   */
  def applyTransaction(
      state: AccountState,
      tx: Transaction
  ): TransactionResult =
    if tx.amount <= BigDecimal(0) then
      TransactionResult.Rejected(state, tx.id, "Nilai transaksi harus lebih besar dari nol")
    else
      tx.txType match
        case TransactionType.Credit =>
          val updated = state.copy(
            balance = state.balance + tx.amount,
            successfulTxCount = state.successfulTxCount + 1
          )
          TransactionResult.Success(updated, tx.id)

        case TransactionType.Debit =>
          if state.balance >= tx.amount then
            val updated = state.copy(
              balance = state.balance - tx.amount,
              successfulTxCount = state.successfulTxCount + 1
            )
            TransactionResult.Success(updated, tx.id)
          else
            TransactionResult.Rejected(state, tx.id, "Saldo tidak mencukupi untuk penarikan")

  /**
   * Memproses serangkaian transaksi menggunakan Tail Recursion
   * Memastikan O(1) stack space terlepas dari ukuran list.
   */
  def processLedger(
      initialState: AccountState,
      transactions: List[Transaction]
  ): LedgerReport =

    @tailrec
    def processLoop(
        remaining: List[Transaction],
        currentState: AccountState,
        rejectionsAcc: List[(String, String)]
    ): LedgerReport =
      remaining match
        case Nil =>
          // Pembalikan list rejections dilakukan sekali di akhir untuk menjaga konsistensi urutan
          LedgerReport(currentState, rejectionsAcc.reverse)

        case currentTx :: tail =>
          applyTransaction(currentState, currentTx) match
            case TransactionResult.Success(newState, _) =>
              processLoop(tail, newState, rejectionsAcc)

            case TransactionResult.Rejected(sameState, txId, reason) =>
              processLoop(tail, sameState, (txId, reason) :: rejectionsAcc)

    processLoop(transactions, initialState, Nil)

// 3. RUNNER VERIFICATION
object LedgerApp:
  def main(args: Array[String]): Unit =
    val account = AccountState(
      accountId = "ACC-ID-9921",
      balance = BigDecimal(1000.00),
      successfulTxCount = 0,
      failedTxCount = 0
    )

    // Simulasi Batch Transaksi
    val batch: List[Transaction] = List(
      Transaction("TX-001", "ACC-ID-9921", BigDecimal(250.00), TransactionType.Credit),
      Transaction("TX-002", "ACC-ID-9921", BigDecimal(1500.00), TransactionType.Debit), // Ditolak (Saldo: 1250)
      Transaction("TX-003", "ACC-ID-9921", BigDecimal(500.00), TransactionType.Debit),  // Berhasil (Saldo sisa: 750)
      Transaction("TX-004", "ACC-ID-9921", BigDecimal(-50.00), TransactionType.Credit)  // Ditolak (Amount invalid)
    )

    val report = TransactionEngine.processLedger(account, batch)

    println("=== HASIL PROSES LEDGER (AUDIT LOG) ===")
    println(s"Account ID        : ${report.finalState.accountId}")
    println(s"Final Balance     : $$${report.finalState.balance}")
    println(s"Sukses Terproses  : ${report.finalState.successfulTxCount}")
    println(s"Gagal Terproses   : ${report.rejectedTransactions.size}")
    
    println("\nRincian Penolakan:")
    report.rejectedTransactions.foreach { case (id, reason) =>
      println(s"- ID: $id | Alasan: $reason")
    }

    // Bukti Immutability Objek Awal
    println("\n=== INTEGRITAS DATA AWAL ===")
    println(s"Saldo Awal Objek Account: $$${account.balance}")
    assert(account.balance == BigDecimal(1000.00), "FATAL: Objek awal termutasi!")
