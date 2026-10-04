// lib/features/trading/trading_engine.dart
import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:rxdart/rxdart.dart';

// Domain Entities
@immutable
final class TickerPrice {
  final String symbol;
  final double price;
  final int timestampMs;

  const TickerPrice({
    required this.symbol,
    required this.price,
    required this.timestampMs,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TickerPrice &&
          runtimeType == other.runtimeType &&
          symbol == other.symbol &&
          price == other.price &&
          timestampMs == other.timestampMs;

  @override
  int get hashCode => symbol.hashCode ^ price.hashCode ^ timestampMs.hashCode;
}

// Events
@immutable
sealed class TradingEvent {
  const TradingEvent();
}

final class RealtimeTickReceived extends TradingEvent {
  final TickerPrice tick;
  const RealtimeTickReceived(this.tick);
}

final class ExecuteMarketOrder extends TradingEvent {
  final String orderId;
  final String symbol;
  final double amount;
  const ExecuteMarketOrder({
    required this.orderId,
    required this.symbol,
    required this.amount,
  });
}

// State
enum OrderExecutionPhase { idle, executing, confirmed, rejected }

@immutable
final class TradingState {
  final TickerPrice? latestTick;
  final OrderExecutionPhase executionPhase;
  final String? lastOrderId;
  final String? failureReason;

  const TradingState({
    this.latestTick,
    this.executionPhase = OrderExecutionPhase.idle,
    this.lastOrderId,
    this.failureReason,
  });

  TradingState copyWith({
    TickerPrice? latestTick,
    OrderExecutionPhase? executionPhase,
    String? lastOrderId,
    String? failureReason,
  }) {
    return TradingState(
      latestTick: latestTick ?? this.latestTick,
      executionPhase: executionPhase ?? this.executionPhase,
      lastOrderId: lastOrderId ?? this.lastOrderId,
      failureReason: failureReason ?? this.failureReason,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is TradingState &&
          runtimeType == other.runtimeType &&
          latestTick == other.latestTick &&
          executionPhase == other.executionPhase &&
          lastOrderId == other.lastOrderId &&
          failureReason == other.failureReason;

  @override
  int get hashCode =>
      latestTick.hashCode ^
      executionPhase.hashCode ^
      lastOrderId.hashCode ^
      failureReason.hashCode;
}

// Custom Transformer untuk Throttling High Frequency Socket
EventTransformer<E> throttleWindow<E>(Duration duration) {
  return (events, mapper) {
    return events.throttleTime(duration).flatMap(mapper);
  };
}

// BLoC Implementation
class TradingBloc extends Bloc<TradingEvent, TradingState> {
  final Stream<TickerPrice> _priceStream;
  final Future<void> Function(String id, String symbol, double amt) _tradeApi;
  StreamSubscription<TickerPrice>? _socketSubscription;

  TradingBloc({
    required Stream<TickerPrice> priceStream,
    required Future<void> Function(String id, String symbol, double amt) tradeApi,
  })  : _priceStream = priceStream,
        _tradeApi = tradeApi,
        super(const TradingState()) {
    
    // Proteksi UI dari render loop: Throttle ke 50ms (~20 updates/sec maks)
    on<RealtimeTickReceived>(
      _onRealtimeTickReceived,
      transformer: throttleWindow(const Duration(milliseconds: 50)),
    );

    // Sekuensial: Jamin order dieksekusi berurutan tanpa jumping
    on<ExecuteMarketOrder>(
      _onExecuteMarketOrder,
    );

    _listenToMarketSocket();
  }

  void _listenToMarketSocket() {
    _socketSubscription = _priceStream.listen(
      (tick) => add(RealtimeTickReceived(tick)),
      onError: (err) => addError(err),
      cancelOnError: false,
    );
  }

  void _onRealtimeTickReceived(
    RealtimeTickReceived event,
    Emitter<TradingState> emit,
  ) {
    // Hindari emit jika harga tidak bergeser secara signifikan
    if (state.latestTick != null &&
        state.latestTick!.price == event.tick.price) {
      return;
    }
    emit(state.copyWith(latestTick: event.tick));
  }

  Future<void> _onExecuteMarketOrder(
    ExecuteMarketOrder event,
    Emitter<TradingState> emit,
  ) async {
    // Idempotency check: Jangan jalankan order yang sama dua kali
    if (state.executionPhase == OrderExecutionPhase.executing &&
        state.lastOrderId == event.orderId) {
      return;
    }

    emit(state.copyWith(
      executionPhase: OrderExecutionPhase.executing,
      lastOrderId: event.orderId,
      failureReason: null,
    ));

    try {
      await _tradeApi(event.orderId, event.symbol, event.amount);
      emit(state.copyWith(
        executionPhase: OrderExecutionPhase.confirmed,
      ));
    } catch (e) {
      emit(state.copyWith(
        executionPhase: OrderExecutionPhase.rejected,
        failureReason: e.toString(),
      ));
    }
  }

  @override
  Future<void> close() async {
    await _socketSubscription?.cancel();
    return super.close();
  }
}
