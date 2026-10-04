// TelematicsCore.ts
import {
  NativeModules,
  NativeEventEmitter,
  Platform,
  PermissionsAndroid,
  AppState,
  AppStateStatus,
} from 'react-native';

export interface TelemetryPacket {
  latitude: number;
  longitude: number;
  accuracy: number;
  speed: number;
  maxGForce: number;
  timestamp: number;
  anomalyDetected: boolean;
}

interface NativeTelematicsBridge {
  startTelemetryDaemon(config: {
    notificationTitle: string;
    notificationBody: string;
    sampleRateHz: number;
    gForceThreshold: number;
  }): Promise<boolean>;
  stopTelemetryDaemon(): Promise<boolean>;
  flushRingBuffer(): Promise<TelemetryPacket[]>;
}

const { TelematicsBridgeModule } = NativeModules;
const telematicsEmitter = new NativeEventEmitter(TelematicsBridgeModule);

export class TelematicsEngine {
  private static instance: TelematicsEngine;
  private isProcessing: boolean = false;
  private appState: AppStateStatus = AppState.currentState;

  private constructor() {
    this.setupLifecycleHooks();
  }

  public static getEngine(): TelematicsEngine {
    if (!TelematicsEngine.instance) {
      TelematicsEngine.instance = new TelematicsEngine();
    }
    return TelematicsEngine.instance;
  }

  private setupLifecycleHooks(): void {
    AppState.addEventListener('change', (nextState: AppStateStatus) => {
      // Menangani transisi state aplikasi untuk logging atau optimasi non-kritis
      this.appState = nextState;
    });
  }

  public async requestRequiredPermissions(): Promise<boolean> {
    if (Platform.OS === 'android') {
      const fineLocationGranted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
        {
          title: 'Izin Akses Lokasi Presisi Tinggi Diperlukan',
          message: 'Sistem Telematika memerlukan akses GPS untuk audit keselamatan armada.',
          buttonPositive: 'Beri Izin',
        }
      );

      if (fineLocationGranted !== PermissionsAndroid.RESULTS.GRANTED) {
        return false;
      }

      // Android 10+ (API Level 29) memerlukan izin background location eksplisit terpisah
      if (Platform.Version >= 29) {
        const bgGranted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_BACKGROUND_LOCATION,
          {
            title: 'Izin Lokasi Latar Belakang Diperlukan',
            message: 'Telematika harus tetap aktif saat aplikasi diminimalkan.',
            buttonPositive: 'Izinkan Sepanjang Waktu',
          }
        );
        if (bgGranted !== PermissionsAndroid.RESULTS.GRANTED) {
          return false;
        }
      }

      // Android 13+ (API Level 33) memerlukan runtime izin notifikasi untuk Foreground Service
      if (Platform.Version >= 33) {
        const notificationGranted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS
        );
        if (notificationGranted !== PermissionsAndroid.RESULTS.GRANTED) {
          return false;
        }
      }

      return true;
    }

    if (Platform.OS === 'ios') {
      // iOS permission handled via Info.plist runtime triggers pada native call
      return true;
    }

    return false;
  }

  public async initializeTelemetryPipeline(
    onCriticalEvent: (event: TelemetryPacket) => void
  ): Promise<void> {
    const hasPermission = await this.requestRequiredPermissions();
    if (!hasPermission) {
      throw new Error('Sistem izin ditolak oleh pengguna. Pipeline gagal dimulai.');
    }

    try {
      // Hubungkan event listener untuk anomali telemetri (misal: Crash Detection)
      telematicsEmitter.addListener('onTelemetryAnomaly', onCriticalEvent);

      await TelematicsBridgeModule.startTelemetryDaemon({
        notificationTitle: 'Telematika Armada Aktif',
        notificationBody: 'Memantau akselerasi sensorik dan koordinat telematika.',
        sampleRateHz: 50, // 50 Hz internal buffer sampling
        gForceThreshold: 2.5, // 2.5G trigger threshold untuk crash/hard braking
      });

      this.isProcessing = true;
    } catch (nativeException) {
      telematicsEmitter.removeAllListeners('onTelemetryAnomaly');
      this.isProcessing = false;
      throw new Error(`Inisialisasi Native Daemon Gagal: ${nativeException}`);
    }
  }

  public async terminatePipeline(): Promise<void> {
    if (!this.isProcessing) return;

    try {
      await TelematicsBridgeModule.stopTelemetryDaemon();
    } finally {
      telematicsEmitter.removeAllListeners('onTelemetryAnomaly');
      this.isProcessing = false;
    }
  }

  public async pullTelemetryBatch(): Promise<TelemetryPacket[]> {
    if (!this.isProcessing) {
      return [];
    }
    // Menarik isi data buffer tanpa memblokir native sensor writing thread
    return await TelematicsBridgeModule.flushRingBuffer();
  }
}
