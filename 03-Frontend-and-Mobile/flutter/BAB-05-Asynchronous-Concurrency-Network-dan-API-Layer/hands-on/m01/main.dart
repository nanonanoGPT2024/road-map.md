// secure_network_client.dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:flutter/foundation.dart';
import 'portfolio_payload.dart';

/// Secure Token Provider Contract
abstract class ITokenRepository {
  Future<String?> getAccessToken();
  Future<String?> getRefreshToken();
  Future<String> refreshAccessToken(String refreshToken);
  Future<void> clearSession();
}

/// Dynamic SSL Pinning & Enterprise Configured Dio Client
class EnterpriseApiClient {
  late final Dio _dio;
  final ITokenRepository _tokenRepository;
  final Completer<void>? _refreshCompleter = null;

  EnterpriseApiClient({
    required String baseUrl,
    required ITokenRepository tokenRepository,
    required List<String> allowedSha256Fingerprints,
  }) : _tokenRepository = tokenRepository {
    final BaseOptions options = BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      sendTimeout: const Duration(seconds: 10),
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      responseType: ResponseType.json,
    );

    _dio = Dio(options);

    _configureSslPinning(allowedSha256Fingerprints);
    _configureInterceptors();
  }

  void _configureSslPinning(List<String> allowedFingerprints) {
    if (kIsWeb) return; // Web mengandalkan native browser certificate validation

    _dio.httpClientAdapter = IOHttpClientAdapter(
      createHttpClient: () {
        final SecurityContext securityContext = SecurityContext(withTrustedRoots: true);
        final HttpClient client = HttpClient(context: securityContext);

        client.badCertificateCallback = (X509Certificate cert, String host, int port) {
          // Konversi SHA-256 DER bytes ke format hex string standar
          final certSha256 = cert.sha256.map((b) => b.toRadixString(16).padLeft(2, '0')).join(':').toUpperCase();
          
          final isMatched = allowedFingerprints.any(
            (fingerprint) => fingerprint.toUpperCase() == certSha256,
          );

          if (!isMatched) {
            // Drop koneksi secara langsung jika certificate fingerprint tidak cocok
            return false;
          }
          return true;
        };
        return client;
      },
    );
  }

  void _configureInterceptors() {
    _dio.interceptors.addAll([
      // 1. Auth & Queue Token Interceptor
      QueuedInterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _tokenRepository.getAccessToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException err, handler) async {
          if (err.response?.statusCode == 401) {
            final RequestOptions requestOptions = err.requestOptions;
            
            try {
              final refreshToken = await _tokenRepository.getRefreshToken();
              if (refreshToken == null) {
                await _tokenRepository.clearSession();
                return handler.next(err);
              }

              // QueuedInterceptorsWrapper mengunci semua request lain saat pemanggilan di bawah berlangsung
              final newAccessToken = await _tokenRepository.refreshAccessToken(refreshToken);

              // Update header authorization dengan token baru
              requestOptions.headers['Authorization'] = 'Bearer $newAccessToken';

              // Eksekusi ulang request yang gagal
              final response = await _dio.fetch(requestOptions);
              return handler.resolve(response);
            } catch (refreshErr) {
              await _tokenRepository.clearSession();
              return handler.next(err);
            }
          }
          return handler.next(err);
        },
      ),

      // 2. Exponential Backoff with Jitter Retry Interceptor
      InterceptorsWrapper(
        onError: (DioException err, handler) async {
          if (_shouldRetry(err)) {
            final requestOptions = err.requestOptions;
            final currentAttempt = (requestOptions.extra['retry_attempt'] as int? ?? 0);
            const maxRetries = 3;

            if (currentAttempt < maxRetries) {
              requestOptions.extra['retry_attempt'] = currentAttempt + 1;
              
              final delay = _calculateJitterDelay(currentAttempt);
              await Future.delayed(delay);

              try {
                final response = await _dio.fetch(requestOptions);
                return handler.resolve(response);
              } catch (retryErr) {
                if (retryErr is DioException) {
                  return handler.next(retryErr);
                }
              }
            }
          }
          return handler.next(err);
        },
      ),
    ]);
  }

  bool _shouldRetry(DioException err) {
    return err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        err.type == DioExceptionType.connectionError ||
        (err.response != null && err.response!.statusCode! >= 500);
  }

  Duration _calculateJitterDelay(int attempt) {
    const int baseDelayMs = 1000;
    const int maxDelayMs = 10000;
    final int exponentialBackoff = baseDelayMs * pow(2, attempt).toInt();
    final int ceiling = min(exponentialBackoff, maxDelayMs);
    final int jittered = Random().nextInt(ceiling + 1);
    return Duration(milliseconds: jittered);
  }

  /// Request Method dengan Isolasi Parsing CPU-Bound
  Future<PortfolioResponse> getPortfolio(String portfolioId) async {
    final response = await _dio.get<dynamic>('/v1/portfolios/$portfolioId');

    // Mencegah Jank: Eksekusi mapping data mentah ke DTO di dalam Background Isolate
    final parsedData = await compute(_parsePortfolioBackground, response.data);
    return parsedData;
  }
}

/// Fungsi Parsing Top-Level/Static untuk compute()
PortfolioResponse _parsePortfolioBackground(dynamic rawData) {
  Map<String, dynamic> jsonMap;
  if (rawData is String) {
    jsonMap = jsonDecode(rawData) as Map<String, dynamic>;
  } else if (rawData is Map<String, dynamic>) {
    jsonMap = rawData;
  } else {
    throw const FormatException('Payload format is invalid');
  }
  return PortfolioResponse.fromJson(jsonMap);
}
