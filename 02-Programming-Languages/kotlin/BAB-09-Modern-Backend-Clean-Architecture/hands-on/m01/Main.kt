package com.ecommerce.application.service

import com.ecommerce.application.dto.CheckoutCommand
import com.ecommerce.application.dto.CheckoutResult
import com.ecommerce.application.port.CheckoutUseCase
import com.ecommerce.application.port.InventoryPort
import com.ecommerce.application.port.OrderRepositoryPort
import com.ecommerce.application.port.PaymentGatewayPort
import com.ecommerce.domain.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class CheckoutService(
    private val inventoryPort: InventoryPort,
    private val paymentGatewayPort: PaymentGatewayPort,
    private val orderRepository: OrderRepositoryPort
) : CheckoutUseCase {

    override suspend fun execute(command: CheckoutCommand): Result<CheckoutResult> = withContext(Dispatchers.Default) {
        val allocatedItems = mutableListOf<Pair<ProductId, Quantity>>()

        try {
            // 1. Validasi & Amankan Stok (Two-Phase style rollback jika gagal)
            val orderLines = command.items.map { item ->
                val pId = ProductId(item.productId)
                val qty = Quantity(item.quantity)

                val unitPrice = inventoryPort.getUnitPrice(pId)
                    ?: throw NoSuchElementException("Produk ${item.productId} tidak ditemukan.")

                val reserved = inventoryPort.reserveStock(pId, qty)
                if (!reserved) {
                    throw IllegalStateException("Stok produk ${item.productId} tidak mencukupi.")
                }

                allocatedItems.add(pId to qty)
                OrderLine(pId, unitPrice, qty)
            }

            // 2. Bangun Pure Domain Aggregate
            val order = Order.create(
                id = OrderId.new(),
                customerId = command.customerId,
                items = orderLines
            )

            // 3. Simpan state Order
            orderRepository.save(order).getOrThrow()

            // 4. Request Payment Gateway Intent
            val paymentToken = paymentGatewayPort.createPaymentIntent(
                orderId = order.id.value.toString(),
                amount = order.totalAmount
            ).getOrThrow()

            // 5. Kembalikan representasi DTO
            Result.success(
                CheckoutResult(
                    orderId = order.id.value,
                    totalAmount = order.totalAmount.amount,
                    currency = order.totalAmount.currency,
                    paymentRedirectUrl = "https://payment.gateway.internal/checkout/$paymentToken"
                )
            )
        } catch (ex: Exception) {
            // Kompensasi Transaksi (Compensating Transaction) jika salah satu langkah gagal
            allocatedItems.forEach { (pId, qty) ->
                inventoryPort.releaseStock(pId, qty)
            }
            Result.failure(ex)
        }
    }
}
