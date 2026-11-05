import AppIntents
import AppIntentsKit
import Domain
import SwiftUI

public struct ItemListView: View {
    @Environment(ItemService.self) private var service
    @State private var isAdding = false

    public init() {}

    public var body: some View {
        NavigationStack {
            List(service.items) { item in
                ItemRow(item: item)
            }
            .overlay {
                if service.items.isEmpty {
                    EmptyItemsView()
                }
            }
            .navigationTitle(Text(.copy("Items")))
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    // 閉じた Duo では縦のバーやメニューに移るので、画像だけにせずタイトルを持たせる
                    Button {
                        isAdding = true
                    } label: {
                        Label {
                            Text(.copy("Add"))
                        } icon: {
                            Image(systemName: "plus")
                        }
                    }
                }
            }
            .sheet(isPresented: $isAdding) {
                AddItemSheet()
            }
        }
    }
}

struct ItemRow: View {
    let item: Item

    var body: some View {
        VStack(alignment: .leading) {
            Text(verbatim: item.title)
            if let dueDate = item.dueDate {
                Text(dueDate, format: .dateTime.year().month().day())
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct EmptyItemsView: View {
    var body: some View {
        ContentUnavailableView {
            Label {
                Text(.copy("No Items"))
            } icon: {
                Image(systemName: "tray")
            }
        }
    }
}

struct AddItemSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(ItemService.self) private var service
    @State private var title = ""

    var body: some View {
        NavigationStack {
            Form {
                TextField(text: $title) {
                    Text(.copy("Title"))
                }
            }
            .navigationTitle(Text(.copy("New Item")))
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(role: .cancel) {
                        dismiss()
                    } label: {
                        Text(.copy("Cancel"))
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    // アプリ内のボタンも Intent を通す。Siri やショートカットと同じ経路になる
                    Button(intent: AddItemIntent(title: title)) {
                        Text(.copy("Add"))
                    }
                    .disabled(title.isEmpty)
                }
            }
            .onChange(of: service.items.count) {
                dismiss()
            }
        }
    }
}
