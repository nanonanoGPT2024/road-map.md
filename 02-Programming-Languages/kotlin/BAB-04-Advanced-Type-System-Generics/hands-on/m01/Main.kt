package com.architecture.generics.eventbus

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList
import kotlin.reflect.KClass

// 1. Domain Event Hierarchy
interface DomainEvent {
    val eventId: String
    val timestamp: Long
}

data class OrderCreatedEvent(
    override val eventId: String,
    override val timestamp: Long,
    val orderId: String,
    val amountCents: Long
) : DomainEvent

data class FraudDetectedEvent(
    override val eventId: String,
    override val timestamp: Long,
    val riskScore: Double
) : DomainEvent

// 2. Contravariant Event Listener (Consumer)
fun interface EventListener<in E : DomainEvent> {
    fun onEvent(event: E)
}

// 3. Covariant Event Envelope (Producer)
interface EventEnvelope<out E : DomainEvent> {
    val traceId: String
    val payload: E
}

private class EventEnvelopeImpl<out E : DomainEvent>(
    override val traceId: String,
    override val payload: E
) : EventEnvelope<E>

// 4. Central Type-Safe Event Bus
class TypeSafeEventBus {
    // Menyimpan mapping KClass ke daftar listener invarian berbasis Star-Projection
    private val subscribers = ConcurrentHashMap<KClass<*>, CopyOnWriteArrayList<EventListener<*>>>()

    // Registrasi bertipe reified (Use-Site & Runtime Reification)
    inline fun <reified E : DomainEvent> subscribe(listener: EventListener<E>) {
        subscribeInternal(E::class, listener)
    }

    @PublishedApi
    internal fun <E : DomainEvent> subscribeInternal(clazz: KClass<E>, listener: EventListener<E>) {
        val list = subscribers.computeIfAbsent(clazz) { CopyOnWriteArrayList() }
        list.add(listener)
    }

    // Publish dengan kovariansi penuh
    @Suppress("UNCHECKED_CAST")
    fun <E : DomainEvent> publish(event: E) {
        val targetClass = event::class
        val listeners = subscribers[targetClass] ?: return
        
        for (rawListener in listeners) {
            // Unchecked cast internal aman karena registrasi diisolasi oleh generic contract subscribeInternal
            val listener = rawListener as EventListener<E>
            listener.onEvent(event)
        }
    }

    // Envelope Factory Pattern memanfaatkan Covariance
    fun <E : DomainEvent> wrap(traceId: String, event: E): EventEnvelope<E> {
        return EventEnvelopeImpl(traceId, event)
    }

    // Polimorphic Envelope Processing
    fun processEnvelope(envelope: EventEnvelope<DomainEvent>) {
        println("Processing Trace [${envelope.traceId}] for Event [${envelope.payload.eventId}]")
        publish(envelope.payload)
    }
}

// 5. Eksekusi End-to-End
fun main() {
    val bus = TypeSafeEventBus()

    // Registrasi Listener Tipe Spesifik
    bus.subscribe<OrderCreatedEvent> { event ->
        println("Order Handler: Order ${event.orderId} processed with amount: ${event.amountCents}")
    }

    // Registrasi General Domain Listener via Consumer Polymorphism
    val genericListener = EventListener<DomainEvent> { event ->
        println("Audit Logger: Generic Event Received: ${event.eventId} at ${event.timestamp}")
    }
    
    // DomainEvent listener dapat menangani OrderCreatedEvent secara valid
    bus.subscribeInternal(OrderCreatedEvent::class, genericListener)

    // Penerbitan Event Konkret
    val orderEvent = OrderCreatedEvent(
        eventId = "EVT-9001",
        timestamp = System.currentTimeMillis(),
        orderId = "ORD-4412",
        amountCents = 150_000
    )

    // Covariance Proof:
    // EventEnvelopeImpl<OrderCreatedEvent> dapat dilempar ke fungsi yang meminta EventEnvelope<DomainEvent>
    val envelope: EventEnvelope<OrderCreatedEvent> = bus.wrap("TRACE-XYZ-88", orderEvent)
    bus.processEnvelope(envelope)
}
