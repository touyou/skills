import AppIntents
@testable import AppIntentsKit
import Domain
import Foundation
import Persistence
import Synchronization
import Testing

final class InMemoryItemStore: ItemStore {
    private let storage = Mutex<[Item]>([])

    var saved: [Item] {
        storage.withLock { $0 }
    }

    func load() throws -> [Item] {
        storage.withLock { $0 }
    }

    func save(_ items: [Item]) throws {
        storage.withLock { $0 = items }
    }
}

@MainActor
struct ItemServiceTests {
    @Test func addingAnItemSavesIt() throws {
        let store = InMemoryItemStore()
        let service = ItemService(store: store)

        try service.add(title: "Patch", dueDate: nil)

        #expect(store.saved.map(\.title) == ["Patch"])
        #expect(service.items.map(\.title) == ["Patch"])
    }

    @Test func writingIntentsArePinnedToTheApp() {
        #expect(AddItemIntent.allowedExecutionTargets == [.main])
        #expect(GetItemCountIntent.allowedExecutionTargets == [.main])
    }
}
