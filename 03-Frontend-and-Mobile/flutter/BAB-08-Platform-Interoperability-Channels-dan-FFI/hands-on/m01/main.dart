========================================================================================================================
                                      FLUTTER NATIVE INTEROPERABILITY PIPELINE
========================================================================================================================

   [ DART LAYER ]
         |
         +-----> (A) Platform Channel Path: MethodChannel.invokeMethod('processData', payload)
         |            |
         |            v
         |       StandardMethodCodec / StandardMessageCodec
         |       (Serialisasi Objek Dart -> Binary Data: ByteBuffer)
         |            |
         |            v
         |       BinaryMessages.send('channel_name', byteBuffer)
         |            |
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   [ DART VM / C++ ENGINE BOUNDARY ]
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
         |            v
         |       flutter::PlatformView::SendPlatformMessage
         |            |
         |            v
         |       TaskRunner Switch: TaskRunners::GetPlatformTaskRunner()
         |       (Thread Hop: Engine Raster/UI Thread ---> Platform Main Thread)
         |            |
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   [ HOST PLATFORM OS ]
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
         |            +--------------------------------------------+
         |            |                                            |
         |            v (Android)                                  v (iOS)
         |       JNI Envoy Call                               Native Message Handler
         |            |                                            |
         |       FlutterJNI.handlePlatformMessage()           FlutterEngine.sendPlatformMessage()
         |            |                                            |
         |       MethodChannel.MethodCallHandler              FlutterMethodCallHandler
         |            |                                            |
         |       Platform Thread Menjalankan Operasi Native   Platform Thread Menjalankan Operasi Native
         |
         |
         +-----> (B) Direct Memory FFI Path: DynamicLibrary.lookupFunction<NativeFn, DartFn>('processRawData')
                      |
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   [ DIRECT DART VM C-CALL (NO ENGINE INTERMEDIARY, ZERO SERIALIZATION) ]
  ~~~~~~~~~~~~~~~~~~~~|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                      |
                      v
                 Direct Pointer Address Resolution (Memory Address: 0x7FFF5BE0)
                      |
                      v
                 Native C/C++/Rust Execution (.so / .dylib)
                 (Berjalan pada Isolate Thread atau C Background Thread)
                      |
                      v
                 Return Struct Value / Direct Memory Mutation
========================================================================================================================
