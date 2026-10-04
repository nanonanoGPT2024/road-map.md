import SwiftUI
import SwiftData

public struct TaskListView: View {
    @Environment(\.modelContext) private var mainModelContext
    
    // UI selalu mengamati local DB, menghasilkan 0ms optimistic visual update
    @Query(sort: \ProjectTaskItem.updatedAt, order: .reverse)
    private var tasks: [ProjectTaskItem]
    
    @State private var networkMonitor = NetworkMonitor.shared
    @State private var synchronizer: BackgroundDataSynchronizer?
    @State private var isShowingCreateSheet = false
    @State private var newTitle = ""
    @State private var newNotes = ""
    
    public init() {}
    
    public var body: some View {
        NavigationStack {
            List {
                Section(header: NetworkStatusBar(isConnected: networkMonitor.isConnected)) {
                    ForEach(tasks) { item in
                        TaskRowView(item: item)
                    }
                    .onDelete(perform: deleteItems)
                }
            }
            .navigationTitle("AeroInspect Tasks")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        isShowingCreateSheet = true
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .font(.title3)
                    }
                }
                ToolbarItem(placement: .topBarLeading) {
                    Button("Sync Now") {
                        triggerManualSync()
                    }
                    .disabled(!networkMonitor.isConnected)
                }
            }
            .sheet(isPresented: $isShowingCreateSheet) {
                NavigationStack {
                    Form {
                        TextField("Judul Tugas", text: $newTitle)
                        TextField("Catatan", text: $newNotes)
                    }
                    .navigationTitle("Tugas Baru")
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Batal") { isShowingCreateSheet = false }
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Simpan") {
                                saveTaskOptimistically()
                                isShowingCreateSheet = false
                            }
                            .disabled(newTitle.trimmingCharacters(in: .whitespaces).isEmpty)
                        }
                    }
                }
            }
            .task {
                let networkClient = ProductionNetworkClient()
                synchronizer = BackgroundDataSynchronizer(
                    modelContainer: mainModelContext.container,
                    networkClient: networkClient
                )
                if networkMonitor.isConnected {
                    triggerManualSync()
                }
            }
            .onChange(of: networkMonitor.isConnected) { _, isNowConnected in
                if isNowConnected {
                    triggerManualSync()
                }
            }
        }
    }
    
    private func saveTaskOptimistically() {
        let taskTitle = newTitle
        let taskNotes = newNotes
        newTitle = ""
        newNotes = ""
        
        Task {
            guard let synchronizer else { return }
            do {
                let newId = UUID()
                try await synchronizer.enqueueTaskCreation(
                    id: newId,
                    title: taskTitle,
                    notes: taskNotes
                )
                if networkMonitor.isConnected {
                    _ = try await synchronizer.processPendingMutations()
                }
            } catch {
                print("Error enqueueing task: \(error.localizedDescription)")
            }
        }
    }
    
    private func deleteItems(at offsets: IndexSet) {
        for index in offsets {
            let task = tasks[index]
            mainModelContext.delete(task)
        }
        try? mainModelContext.save()
    }
    
    private func triggerManualSync() {
        Task {
            guard let synchronizer else { return }
            do {
                _ = try await synchronizer.processPendingMutations()
            } catch {
                print("Sync failed: \(error.localizedDescription)")
            }
        }
    }
}

public struct NetworkStatusBar: View {
    public let isConnected: Bool
    
    public var body: some View {
        HStack {
            Circle()
                .fill(isConnected ? Color.green : Color.red)
                .frame(width: 8, height: 8)
            Text(isConnected ? "ONLINE — PIPELINE TERHUBUNG" : "OFFLINE — PERUBAHAN TERSIMPAN LOKAL")
                .font(.caption2)
                .fontWeight(.bold)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

public struct TaskRowView: View {
    let item: ProjectTaskItem
    
    public var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(item.title)
                    .font(.headline)
                if !item.notes.isEmpty {
                    Text(item.notes)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            Spacer()
            SyncIndicatorBadge(state: item.syncState)
        }
    }
}

public struct SyncIndicatorBadge: View {
    let state: SyncState
    
    public var body: some View {
        switch state {
        case .synced:
            Image(systemName: "checkmark.icloud.fill")
                .foregroundColor(.blue)
        case .pendingCreation, .pendingUpdate:
            Image(systemName: "arrow.triangle.2.circlepath.icloud.fill")
                .foregroundColor(.orange)
        case .pendingDeletion:
            Image(systemName: "trash.circle.fill")
                .foregroundColor(.red)
        }
    }
}
