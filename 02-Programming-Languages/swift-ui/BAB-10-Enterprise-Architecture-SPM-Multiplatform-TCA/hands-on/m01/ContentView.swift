// Sources/PortfolioFeature/PortfolioView.swift
import SwiftUI
import ComposableArchitecture
import SharedModels

public struct PortfolioView: View {
    @Bindable var store: StoreOf<PortfolioFeature>
    
    public init(store: StoreOf<PortfolioFeature>) {
        self.store = store
    }
    
    public var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Header Metrik Bersama
                VStack(alignment: .leading, spacing: 4) {
                    Text("Total Nilai Portofolio")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    
                    Text(store.totalPortfolioValue, format: .currency(code: "USD"))
                        .font(.system(size: 32, weight: .bold, design: .rounded))
                    
                    HStack {
                        Circle()
                            .fill(store.isStreamingActive ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text(store.isStreamingActive ? "Live Ticker Connected" : "Disconnected")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(Color(.secondarySystemBackground))
                
                // Asset List / Table
                #if os(macOS)
                macOSTableLayout
                #else
                iOSListLayout
                #endif
            }
            .navigationTitle("Executive Wealth")
            .onAppear { store.send(.onAppear) }
            .onDisappear { store.send(.onDisappear) }
            .alert(
                "Pemberitahuan Sistem",
                isPresented: Binding(
                    get: { store.alertMessage != nil },
                    set: { if !$0 { store.send(.dismissAlert) } }
                )
            ) {
                Button("OK", role: .cancel) { store.send(.dismissAlert) }
            } message: {
                Text(store.alertMessage ?? "")
            }
        }
    }
    
    #if os(iOS)
    private var iOSListLayout: some View {
        List(store.assets) { asset in
            HStack {
                VStack(alignment: .leading) {
                    Text(asset.ticker)
                        .font(.headline)
                    Text("\(asset.allocatedAmount.formatted()) lembar")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text(asset.marketValue, format: .currency(code: "USD"))
                        .font(.body.monospacedDigit())
                        .bold()
                    Text(asset.currentPrice, format: .currency(code: "USD"))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, 4)
        }
        .listStyle(.insetGrouped)
    }
    #endif
    
    #if os(macOS)
    private var macOSTableLayout: some View {
        Table(store.assets) {
            TableColumn("Ticker", value: \.ticker)
                .width(min: 80, ideal: 100)
            
            TableColumn("Alokasi") { asset in
                Text(asset.allocatedAmount.formatted())
                    .monospacedDigit()
            }
            .width(min: 80, ideal: 100)
            
            TableColumn("Harga Pasar") { asset in
                Text(asset.currentPrice, format: .currency(code: "USD"))
                    .monospacedDigit()
            }
            .width(min: 100, ideal: 120)
            
            TableColumn("Total Valuasi") { asset in
                Text(asset.marketValue, format: .currency(code: "USD"))
                    .bold()
                    .monospacedDigit()
            }
            .width(min: 120, ideal: 150)
        }
        .frame(minWidth: 500, minHeight: 300)
    }
    #endif
}
