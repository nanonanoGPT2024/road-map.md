import UIKit
import CoreGraphics
import ImageIO
import OSLog

// MARK: - Thread-Safe Downsampler Cache Engine
public actor OptimizedImagePipeline {
    public static let shared = OptimizedImagePipeline()
    private let signpostLog = OSLog(subsystem: "com.enterprise.media", category: "ImagePipeline")
    
    // In-memory cache yang dibatasi kuota alokasi memori aktual
    private let memoryCache: NSCache<NSURL, UIImage> = {
        let cache = NSCache<NSURL, UIImage>()
        cache.totalCostLimit = 100 * 1024 * 1024 // Batas ketat: 100 Megabytes
        return cache
    }()
    
    private init() {}
    
    /// Melakukan decoding & downsampling gambar secara hemat tanpa memuat full bitmap ke Heap
    public func downsample(
        imageAt sourceURL: URL,
        to targetSize: CGSize,
        scale: CGFloat
    ) async throws -> UIImage {
        let nsURL = sourceURL as NSURL
        if let cached = memoryCache.object(forKey: nsURL) {
            return cached
        }
        
        let signpostID = OSSignpostID(log: signpostLog)
        os_signpost(.begin, log: signpostLog, name: "DownsampleTask", signpostID: signpostID, "URL: %{public}@", sourceURL.lastPathComponent)
        
        defer {
            os_signpost(.end, log: signpostLog, name: "DownsampleTask", signpostID: signpostID)
        }
        
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                let imageSourceOptions = [kCGImageSourceShouldCache: false] as CFDictionary
                guard let imageSource = CGImageSourceCreateWithURL(sourceURL as CFURL, imageSourceOptions) else {
                    continuation.resume(throwing: URLError(.cannotDecodeContentData))
                    return
                }
                
                // Menentukan dimensi target berdasarkan densitas layar hardware
                let maxDimensionInPixels = max(targetSize.width, targetSize.height) * scale
                
                let downsampleOptions = [
                    kCGImageSourceCreateThumbnailFromImageAlways: true,
                    kCGImageSourceShouldCacheImmediately: true, // Dekompresi terjadi di sini (Background)
                    kCGImageSourceCreateThumbnailWithTransform: true,
                    kCGImageSourceThumbnailMaxPixelSize: maxDimensionInPixels
                ] as CFDictionary
                
                guard let downsampledImage = CGImageSourceCreateThumbnailAtIndex(imageSource, 0, downsampleOptions) else {
                    continuation.resume(throwing: URLError(.cannotDecodeContentData))
                    return
                }
                
                let finalImage = UIImage(cgImage: downsampledImage)
                
                // Kalkulasi perkiraan cost byte: lebar * tinggi * 4 (RGBA 8-bit)
                let cost = Int(targetSize.width * scale * targetSize.height * scale * 4)
                Task { [weak self] in
                    await self?.cacheImage(finalImage, for: nsURL, cost: cost)
                }
                
                continuation.resume(returning: finalImage)
            }
        }
    }
    
    private func cacheImage(_ image: UIImage, for url: NSURL, cost: Int) {
        memoryCache.setObject(image, forKey: url, cost: cost)
    }
}

// MARK: - Zero Off-Screen Rendering Custom View Cell
public final class HighPerformanceCatalogCell: UICollectionViewCell {
    public static let reuseIdentifier = "HighPerformanceCatalogCell"
    
    private let thumbnailImageView: UIImageView = {
        let iv = UIImageView()
        iv.translatesAutoresizingMaskIntoConstraints = false
        iv.contentMode = .scaleAspectFill
        // PENTING: Menghindari Off-Screen Render Masking
        // Menggunakan direct corner radius tanpa shadow/clip kombinasi
        iv.layer.cornerRadius = 8.0
        iv.layer.masksToBounds = true
        return iv
    }()
    
    private var currentTask: Task<Void, Never>?
    
    public override init(frame: CGRect) {
        super.init(frame: frame)
        setupViews()
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    private func setupViews() {
        contentView.addSubview(thumbnailImageView)
        NSLayoutConstraint.activate([
            thumbnailImageView.topAnchor.constraint(equalTo: contentView.topAnchor),
            thumbnailImageView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            thumbnailImageView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            thumbnailImageView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor)
        ])
        
        // Optimasi Layer Drawing Pipeline
        layer.drawsAsynchronously = true // Offload drawing composition ke background render thread
    }
    
    public func configure(with imageURL: URL) {
        currentTask?.cancel()
        
        let screenScale = UIScreen.main.scale
        let targetSize = bounds.size == .zero ? CGSize(width: 120, height: 120) : bounds.size
        
        currentTask = Task {
            do {
                let optimizedImage = try await OptimizedImagePipeline.shared.downsample(
                    imageAt: imageURL,
                    to: targetSize,
                    scale: screenScale
                )
                
                if !Task.isCancelled {
                    self.thumbnailImageView.image = optimizedImage
                }
            } catch {
                // Tangani error secara silent atau fallback image
                if !Task.isCancelled {
                    self.thumbnailImageView.image = nil
                }
            }
        }
    }
    
    public override func prepareForReuse() {
        super.prepareForReuse()
        currentTask?.cancel()
        currentTask = nil
        thumbnailImageView.image = nil
    }
}
