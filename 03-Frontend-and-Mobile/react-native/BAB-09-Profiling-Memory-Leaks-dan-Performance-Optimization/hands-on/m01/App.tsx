// components/OrderBookOptimized.tsx
import React, { memo, useRef, useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, LayoutAnimation, Platform } from 'react-native';
import { FlashList, ListRenderItemInfo } from '@shopify/flash-list';

export interface OrderLevel {
  id: string;
  price: number;
  amount: number;
  total: number;
  type: 'ask' | 'bid';
}

interface OrderBookProps {
  streamUrl: string;
}

// 1. Ekstraksi Item Component ter-memoisasi dengan prop komparator presisi
const OrderBookRow = memo(
  ({ item }: { item: OrderLevel }) => {
    return (
      <View style={styles.row}>
        <Text
          style={[
            styles.cell,
            item.type === 'ask' ? styles.askText : styles.bidText,
          ]}
        >
          {item.price.toFixed(2)}
        </Text>
        <Text style={styles.cell}>{item.amount.toFixed(4)}</Text>
        <Text style={[styles.cell, styles.alignRight]}>
          {item.total.toFixed(4)}
        </Text>
      </View>
    );
  },
  (prevProps, nextProps) => {
    // Hindari re-render jika field harga & total identik
    return (
      prevProps.item.id === nextProps.item.id &&
      prevProps.item.amount === nextProps.item.amount &&
      prevProps.item.total === nextProps.item.total
    );
  }
);

export const OrderBookOptimized: React.FC<OrderBookProps> = ({ streamUrl }) => {
  const [orders, setOrders] = useState<OrderLevel[]>([]);
  
  // Menggunakan Ref sebagai Mutable Ring Buffer untuk menghindari GC pressure
  const incomingBufferRef = useRef<OrderLevel[]>([]);
  const frameRequestRef = useRef<number | null>(null);
  const webSocketRef = useRef<WebSocket | null>(null);

  // 2. Scheduler Pembacaan Buffer: Throttling tersinkronisasi dengan Screen Refresh Rate
  const flushBufferToState = useCallback(() => {
    if (incomingBufferRef.current.length > 0) {
      setOrders((prevOrders) => {
        // Terapkan partial mutations atau replace list dengan instansiasi terukur
        const updated = [...incomingBufferRef.current];
        incomingBufferRef.current = []; // Drain buffer
        return updated;
      });
    }
    // Jadwalkan batch flush pada frame berikutnya
    frameRequestRef.current = requestAnimationFrame(flushBufferToState);
  }, []);

  useEffect(() => {
    // Mulai render loop scheduler
    frameRequestRef.current = requestAnimationFrame(flushBufferToState);

    // Setup High-Speed WebSocket Connection
    const ws = new WebSocket(streamUrl);
    webSocketRef.current = ws;

    ws.onmessage = (event: WebSocketMessageEvent) => {
      try {
        const payload: OrderLevel[] = JSON.parse(event.data);
        // MUTASI IN-PLACE PADA BUFFER: Menghindari JS Garbage Collection Cycle berlebih
        incomingBufferRef.current = payload;
      } catch (err) {
        // Drop payload korup tanpa alokasi objek error kompleks
      }
    };

    return () => {
      // TEARDOWN COMPREHENSIVE: Menghindari cross-bridge memory leak
      if (frameRequestRef.current !== null) {
        cancelAnimationFrame(frameRequestRef.current);
      }
      if (webSocketRef.current) {
        webSocketRef.current.onmessage = null;
        webSocketRef.current.onerror = null;
        webSocketRef.current.onclose = null;
        webSocketRef.current.close();
        webSocketRef.current = null;
      }
    };
  }, [streamUrl, flushBufferToState]);

  const renderItem = useCallback(
    ({ item }: ListRenderItemInfo<OrderLevel>) => <OrderBookRow item={item} />,
    []
  );

  const keyExtractor = useCallback((item: OrderLevel) => item.id, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerText}>Price</Text>
        <Text style={styles.headerText}>Amount</Text>
        <Text style={[styles.headerText, styles.alignRight]}>Total</Text>
      </View>
      <FlashList
        data={orders}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        estimatedItemSize={24}
        drawDistance={150}
        removeClippedSubviews={Platform.OS === 'android'}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0e1118' },
  header: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: '#262932',
  },
  headerText: { flex: 1, color: '#848e9c', fontSize: 12, fontWeight: '600' },
  row: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    height: 24,
    alignItems: 'center',
  },
  cell: { flex: 1, fontSize: 12, color: '#d1d4dc', fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace' },
  askText: { color: '#f6465d' },
  bidText: { color: '#0ecb81' },
  alignRight: { textAlign: 'right' },
});
