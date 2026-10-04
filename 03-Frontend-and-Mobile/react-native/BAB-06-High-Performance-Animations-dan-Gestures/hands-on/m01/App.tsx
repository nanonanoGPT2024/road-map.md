// Path: src/components/interactive/EnterpriseBottomSheet.tsx
import React, { useCallback, useId } from 'react';
import {
  Dimensions,
  StyleSheet,
  View,
  Text,
  Pressable,
} from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  interpolate,
  Extrapolation,
  runOnJS,
  useAnimatedReaction,
} from 'react-native-reanimated';

const { height: SCREEN_HEIGHT } = Dimensions.get('window');
const SHEET_MAX_HEIGHT = SCREEN_HEIGHT * 0.75;
const SHEET_MIN_HEIGHT = 100;
const DISMISS_THRESHOLD = 50;

interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export const EnterpriseBottomSheet: React.FC<BottomSheetProps> = ({
  isOpen,
  onClose,
  children,
}) => {
  // Posisi Y vertikal dari sheet. 
  // Nilai 0 merepresentasikan posisi fully open (SHEET_MAX_HEIGHT).
  // Nilai positif merepresentasikan offset ke bawah (tertutup).
  const translateY = useSharedValue<number>(SCREEN_HEIGHT);
  const context = useSharedValue<{ startY: number }>({ startY: 0 });

  const springConfig = {
    damping: 20,
    stiffness: 150,
    mass: 0.8,
    overshootClamping: false,
  };

  // Sinkronisasi prop isOpen dengan animasi native
  useAnimatedReaction(
    () => isOpen,
    (currentIsOpen, previousIsOpen) => {
      'worklet';
      if (currentIsOpen !== previousIsOpen) {
        if (currentIsOpen) {
          translateY.value = withSpring(0, springConfig);
        } else {
          translateY.value = withTiming(SCREEN_HEIGHT, { duration: 250 });
        }
      }
    },
    [isOpen]
  );

  const handleDismissComplete = useCallback(() => {
    onClose();
  }, [onClose]);

  // Algoritma Rubber-Banding Logaritmik (Worklet murni)
  const calculateRubberBanding = (delta: number, dimension: number): number => {
    'worklet';
    const c = 0.55; // Koefisien resistensi iOS standar
    return (delta * dimension * c) / (dimension + c * delta);
  };

  const panGesture = Gesture.Pan()
    .onStart(() => {
      'worklet';
      context.value = { startY: translateY.value };
    })
    .onUpdate((event) => {
      'worklet';
      const rawY = context.value.startY + event.translationY;

      if (rawY < 0) {
        // Efek tarikan ke atas melebihi batas maksimum (Overdrag Rubber-Band)
        const overdrag = -rawY;
        const resisted = calculateRubberBanding(overdrag, SHEET_MAX_HEIGHT);
        translateY.value = -resisted;
      } else {
        translateY.value = rawY;
      }
    })
    .onEnd((event) => {
      'worklet';
      // Kondisi 1: Kecepatan lempar ke bawah tinggi -> Tutup
      if (event.velocityY > 1200) {
        translateY.value = withTiming(
          SCREEN_HEIGHT,
          { duration: 200 },
          (isFinished) => {
            if (isFinished) {
              runOnJS(handleDismissComplete)();
            }
          }
        );
        return;
      }

      // Kondisi 2: Drag melebihi batas threshold -> Tutup
      if (translateY.value > SHEET_MAX_HEIGHT * 0.4) {
        translateY.value = withTiming(
          SCREEN_HEIGHT,
          { duration: 250 },
          (isFinished) => {
            if (isFinished) {
              runOnJS(handleDismissComplete)();
            }
          }
        );
        return;
      }

      // Kondisi 3: Reset kembali ke kondisi Snap Terbuka (0)
      translateY.value = withSpring(0, {
        ...springConfig,
        velocity: event.velocityY,
      });
    });

  const sheetAnimatedStyle = useAnimatedStyle(() => {
    'worklet';
    return {
      transform: [{ translateY: translateY.value }],
    };
  });

  const backdropAnimatedStyle = useAnimatedStyle(() => {
    'worklet';
    const opacity = interpolate(
      translateY.value,
      [0, SHEET_MAX_HEIGHT],
      [0.6, 0],
      Extrapolation.CLAMP
    );

    return {
      opacity,
      pointerEvents: translateY.value >= SHEET_MAX_HEIGHT ? 'none' : 'auto',
    };
  });

  return (
    <View style={StyleSheet.absoluteFillObject} pointerEvents="box-none">
      <Animated.View style={[styles.backdrop, backdropAnimatedStyle]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
      </Animated.View>

      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.sheetContainer, sheetAnimatedStyle]}>
          <View style={styles.handleContainer}>
            <View style={styles.indicator} />
          </View>
          <View style={styles.contentContainer}>{children}</View>
        </Animated.View>
      </GestureDetector>
    </View>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#000',
    zIndex: 10,
  },
  sheetContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: SHEET_MAX_HEIGHT,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    zIndex: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 24,
  },
  handleContainer: {
    width: '100%',
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  indicator: {
    width: 48,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#CBD5E1',
  },
  contentContainer: {
    flex: 1,
    paddingHorizontal: 24,
  },
});
