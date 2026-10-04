import SwiftUI
import WebKit

// MARK: - Platform Aliasing
#if os(iOS)
public typealias PlatformViewRepresentable = UIViewRepresentable
public typealias NativeView = UIView
#elseif os(macOS)
public typealias PlatformViewRepresentable = NSViewRepresentable
public typealias NativeView = NSView
#endif

// MARK: - Core Component
public struct UnifiedWebView: PlatformViewRepresentable {
    public let url: URL
    public let authToken: String?
    @Binding public var isLoading: Bool
    @Binding public var estimatedProgress: Double
    public var onTelemetryReceived: ((String) -> Void)?

    public init(
        url: URL,
        authToken: String? = nil,
        isLoading: Binding<Bool>,
        estimatedProgress: Binding<Double>,
        onTelemetryReceived: ((String) -> Void)? = nil
    ) {
        self.url = url
        self.authToken = authToken
        self._isLoading = isLoading
        self._estimatedProgress = estimatedProgress
        self.onTelemetryReceived = onTelemetryReceived
    }

    // MARK: - Coordinator Factory
    public func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    // MARK: - iOS Implementation
    #if os(iOS)
    public func makeUIView(context: Context) -> WKWebView {
        createAndConfigureWebView(context: context)
    }

    public func updateUIView(_ uiView: WKWebView, context: Context) {
        updateWebViewState(uiView, context: context)
    }

    public static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) {
        tearDownWebView(uiView, coordinator: coordinator)
    }
    #endif

    // MARK: - macOS Implementation
    #if os(macOS)
    public func makeNSView(context: Context) -> WKWebView {
        createAndConfigureWebView(context: context)
    }

    public func updateNSView(_ nsView: WKWebView, context: Context) {
        updateWebViewState(nsView, context: context)
    }

    public static func dismantleNSView(_ nsView: WKWebView, coordinator: Coordinator) {
        tearDownWebView(nsView, coordinator: coordinator)
    }
    #endif

    // MARK: - Shared Configuration Logic
    private func createAndConfigureWebView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        let userContentController = WKUserContentController()

        // Pasang Script Message Handler yang dibungkus Leak-Avoider Proxy
        let handlerProxy = WeakScriptMessageHandler(delegate: context.coordinator)
        userContentController.add(handlerProxy, name: "telemetry")
        configuration.userContentController = userContentController

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator

        // KVO Observers
        context.coordinator.setupObservers(for: webView)

        // Load Request Awal
        var request = URLRequest(url: url)
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        webView.load(request)

        return webView
    }

    private func updateWebViewState(_ webView: WKWebView, context: Context) {
        // Hindari load ulang jika URL tidak berubah
        if webView.url != url && !url.absoluteString.isEmpty {
            var request = URLRequest(url: url)
            if let token = authToken {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
            webView.load(request)
        }
    }

    private static func tearDownWebView(_ webView: WKWebView, coordinator: Coordinator) {
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.configuration.userContentController.removeScriptMessageHandler(forName: "telemetry")
        coordinator.invalidateObservers(for: webView)
    }

    // MARK: - Coordinator Class
    @MainActor
    public final class Coordinator: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        private var parent: UnifiedWebView
        private var progressObservation: NSKeyValueObservation?
        private var loadingObservation: NSKeyValueObservation?

        init(_ parent: UnifiedWebView) {
            self.parent = parent
            super.init()
        }

        func setupObservers(for webView: WKWebView) {
            progressObservation = webView.observe(\.estimatedProgress, options: [.new]) { [weak self] _, change in
                guard let self = self, let newValue = change.newValue else { return }
                Task { @MainActor in
                    self.parent.estimatedProgress = newValue
                }
            }

            loadingObservation = webView.observe(\.isLoading, options: [.new]) { [weak self] _, change in
                guard let self = self, let newValue = change.newValue else { return }
                Task { @MainActor in
                    self.parent.isLoading = newValue
                }
            }
        }

        func invalidateObservers(for webView: WKWebView) {
            progressObservation?.invalidate()
            progressObservation = nil
            loadingObservation?.invalidate()
            loadingObservation = nil
        }

        // WKNavigationDelegate
        public func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            Task { @MainActor in
                self.parent.isLoading = false
            }
        }

        public func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            Task { @MainActor in
                self.parent.isLoading = false
            }
        }

        // WKScriptMessageHandler
        public func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            if message.name == "telemetry", let body = message.body as? String {
                self.parent.onTelemetryReceived?(body)
            }
        }
    }

    // MARK: - Memory Leak Avoider Proxy
    private final class WeakScriptMessageHandler: NSObject, WKScriptMessageHandler {
        private weak var delegate: WKScriptMessageHandler?

        init(delegate: WKScriptMessageHandler) {
            self.delegate = delegate
            super.init()
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            delegate?.userContentController(userContentController, didReceive: message)
        }
    }
}
