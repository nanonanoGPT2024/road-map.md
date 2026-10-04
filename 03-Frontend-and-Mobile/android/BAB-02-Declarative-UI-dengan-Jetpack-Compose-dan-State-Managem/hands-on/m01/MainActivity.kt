package com.enterprise.compose.fintech

import android.os.Parcelable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import kotlinx.collections.immutable.ImmutableList
import kotlinx.collections.immutable.persistentListOf
import kotlinx.collections.immutable.toImmutableList
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.parcelize.Parcelize
import java.math.BigDecimal

// --- DOMAIN CONTRACTS & STATE CONTRACTS ---

@Parcelize
data class CurrencyAmount(
    val amount: BigDecimal,
    val currencyCode: String
) : Parcelable

@Immutable
data class TransactionItem(
    val id: String,
    val title: String,
    val fee: CurrencyAmount
)

sealed interface PaymentUiState {
    val items: ImmutableList<TransactionItem>
    val total: CurrencyAmount

    data class Idle(
        override val items: ImmutableList<TransactionItem>,
        override val total: CurrencyAmount
    ) : PaymentUiState

    data class Processing(
        override val items: ImmutableList<TransactionItem>,
        override val total: CurrencyAmount
    ) : PaymentUiState

    data class Success(
        override val items: ImmutableList<TransactionItem>,
        override val total: CurrencyAmount,
        val transactionReference: String
    ) : PaymentUiState
}

sealed interface PaymentSideEffect {
    data class ShowToast(val message: String) : PaymentSideEffect
    data class NavigateToReceipt(val txHash: String) : PaymentSideEffect
}

// --- ENTERPRISE VIEWMODEL ---

class PaymentEngineViewModel : ViewModel() {

    private val _uiState = MutableStateFlow<PaymentUiState>(
        PaymentUiState.Idle(
            items = persistentListOf(
                TransactionItem("TX-1", "Biaya Langganan Enterprise", CurrencyAmount(BigDecimal("450000.00"), "IDR")),
                TransactionItem("TX-2", "Pajak Pertambahan Nilai (PPN)", CurrencyAmount(BigDecimal("49500.00"), "IDR"))
            ),
            total = CurrencyAmount(BigDecimal("499500.00"), "IDR")
        )
    )
    val uiState: StateFlow<PaymentUiState> = _uiState.asStateFlow()

    private val _effectChannel = Channel<PaymentSideEffect>(Channel.BUFFERED)
    val effect = _effectChannel.receiveAsFlow()

    fun dispatchPaymentIntent() {
        val currentState = _uiState.value
        // Mutex/Lock guard terhadap double-submission
        if (currentState is PaymentUiState.Processing) return

        viewModelScope.launch {
            _uiState.update { 
                PaymentUiState.Processing(it.items, it.total) 
            }

            try {
                // Simulasi Network Call & Cryptographic Signing
                delay(2000)
                val reference = "REF-${System.currentTimeMillis()}"

                _uiState.update { 
                    PaymentUiState.Success(it.items, it.total, reference) 
                }
                _effectChannel.send(PaymentSideEffect.NavigateToReceipt(reference))
            } catch (t: Throwable) {
                _uiState.update { 
                    PaymentUiState.Idle(it.items, it.total) 
                }
                _effectChannel.send(PaymentSideEffect.ShowToast(t.localizedMessage ?: "Kegagalan Sistem"))
            }
        }
    }
}

// --- COMPOSE UI LAYER & CUSTOM SAVER ---

/**
 * Custom Saver untuk menangani preservasi state input dinamis (misal memo voucher).
 */
data class UserDraftNote(val note: String)

val UserDraftNoteSaver = Saver<UserDraftNote, String>(
    save = { it.note },
    restore = { UserDraftNote(it) }
)

@Composable
fun PaymentTransactionScreen(
    viewModel: PaymentEngineViewModel,
    modifier: Modifier = Modifier
) {
    // Collect lifecycle-aware: Mematikan konsumsi saat aplikasi berada di latar belakang
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    // Menggunakan custom saver untuk state lokal independen
    var draftNote by rememberSaveable(saver = UserDraftNoteSaver) {
        UserDraftNote("")
    }

    PaymentScreenContent(
        state = state,
        draftNote = draftNote,
        onDraftNoteChange = { draftNote = UserDraftNote(it) },
        onPayClicked = { viewModel.dispatchPaymentIntent() },
        modifier = modifier
    )
}

@Composable
private fun PaymentScreenContent(
    state: PaymentUiState,
    draftNote: UserDraftNote,
    onDraftNoteChange: (String) -> Unit,
    onPayClicked: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "Ringkasan Pembayaran",
            style = MaterialTheme.typography.headlineMedium
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Render transaksi berbasis Immutable Collection
        TransactionList(items = state.items)

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = draftNote.note,
            onValueChange = onDraftNoteChange,
            label = { Text("Catatan Internal Akuntansi") },
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.weight(1f))

        Text(
            text = "Total: ${state.total.currencyCode} ${state.total.amount}",
            style = MaterialTheme.typography.titleLarge
        )

        Spacer(modifier = Modifier.height(12.dp))

        Button(
            onClick = onPayClicked,
            enabled = state !is PaymentUiState.Processing,
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp)
        ) {
            if (state is PaymentUiState.Processing) {
                CircularProgressIndicator(
                    color = MaterialTheme.colorScheme.onPrimary,
                    modifier = Modifier.size(24.dp)
                )
            } else {
                Text(text = "Eksekusi Pembayaran")
            }
        }
    }
}

@Composable
private fun TransactionList(
    items: ImmutableList<TransactionItem>,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        items.forEach { item ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(text = item.title)
                Text(text = "${item.fee.currencyCode} ${item.fee.amount}")
            }
        }
    }
}
