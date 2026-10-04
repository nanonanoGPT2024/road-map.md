import SwiftUI

// Model data performa tinggi menggunakan unmanaged contiguous buffers
public final class AudioBufferState: ObservableObject {
    public static let sampleCount: Int = 32
    @Published public var spectrumSamples: [Float]

    public init() {
        self.spectrumSamples = Array(repeating: 0.1, count: Self.sampleCount)
    }

    // Simulasi ingestion data dari audio tapping node (CoreAudio/AVFoundation)
    public func updateSamplesDirectly(_ newSamples: [Float]) {
        guard newSamples.count == Self.sampleCount else { return }
        self.spectrumSamples = newSamples
    }
}

public struct MetalAudioVisualizer: View {
    @ObservedObject var audioState: AudioBufferState
    @State private var visualizerScale: CGFloat = 1.0
    private let startTime = Date()

    public init(audioState: AudioBufferState) {
        self.audioState = audioState
    }

    public var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 120.0, paused: false)) { context in
            let elapsedTime = Float(context.date.timeIntervalSince(startTime))
            let maxIntensity = Float(audioState.spectrumSamples.max() ?? 0.1)

            GeometryReader { proxy in
                Canvas(rendersAsynchronously: true) { canvasContext, size in
                    let barWidth = size.width / CGFloat(AudioBufferState.sampleCount)
                    let baseCenterY = size.height / 2.0

                    for i in 0..<AudioBufferState.sampleCount {
                        let amplitude = CGFloat(audioState.spectrumSamples[i])
                        let barHeight = (size.height * 0.4) * amplitude
                        
                        let xPosition = CGFloat(i) * barWidth
                        let rect = CGRect(
                            x: xPosition + 1.0,
                            y: baseCenterY - (barHeight / 2.0),
                            width: max(1.0, barWidth - 2.0),
                            height: barHeight
                        )

                        // Rendering bar spektrum
                        let roundedPath = Path(roundedRect: rect, cornerRadius: 4.0)
                        let gradientColor = Color(
                            hue: Double(i) / Double(AudioBufferState.sampleCount),
                            saturation: 0.8,
                            brightness: 0.95
                        )
                        
                        canvasContext.fill(roundedPath, with: .color(gradientColor))
                    }
                }
                .distortionEffect(
                    ShaderLibrary.audioWaveDistortion(
                        .float2(proxy.size.width, proxy.size.height),
                        .float(elapsedTime),
                        .float(maxIntensity)
                    ),
                    maxSampleOffset: CGSize(width: 30, height: 30)
                )
                .scaleEffect(visualizerScale)
            }
        }
        .drawingGroup() // Force offscreen raster cache layer via Core Graphics / Metal
        .onAppear {
            // Menerapkan Advanced Keyframe / Phase animation pulse
            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                visualizerScale = 1.05
            }
        }
    }
}

// MARK: - Preview Harness with Live Audio Mock Generator
#Preview("Production Audio Visualizer") {
    struct MockContainer: View {
        @StateObject private var bufferState = AudioBufferState()
        let timer = Timer.publish(every: 0.05, on: .main, in: .common).autoconnect()

        var body: some View {
            ZStack {
                Color.black.ignoresSafeArea()
                
                VStack(spacing: 40) {
                    MetalAudioVisualizer(audioState: bufferState)
                        .frame(height: 250)
                        .padding(.horizontal, 20)

                    Text("Metal GPU Native Distortion Active")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundColor(.green)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(Color.green.opacity(0.15))
                        .cornerRadius(20)
                }
            }
            .onReceive(timer) { _ in
                // Menghasilkan fake harmonic data
                var newValues: [Float] = []
                for idx in 0..<AudioBufferState.sampleCount {
                    let pseudoRandom = Float.random(in: 0.15...0.95)
                    let envelope = sin(Float(idx) / Float(AudioBufferState.sampleCount) * .pi)
                    newValues.append(pseudoRandom * envelope)
                }
                bufferState.updateSamplesDirectly(newValues)
            }
        }
    }

    return MockContainer()
}
