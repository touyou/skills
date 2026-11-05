import Domain
import Foundation
import Observation
import Persistence
import WidgetKit

/// 業務ロジックの唯一の入口。Intent と画面はここを通す（ウィジェットは読むだけなので保存先を直接読む）
@MainActor
@Observable
public final class ItemService {
    public private(set) var items: [Item]
    private let store: any ItemStore

    public init(store: any ItemStore) {
        self.store = store
        items = ((try? store.load()) ?? []).sortedByDueDate()
    }

    public func item(id: Item.ID) -> Item? {
        items.first { $0.id == id }
    }

    @discardableResult
    public func add(title: String, dueDate: Date?) throws -> Item {
        let item = Item(title: title, dueDate: dueDate)
        try commit((items + [item]).sortedByDueDate())
        return item
    }

    public func remove(id: Item.ID) throws {
        try commit(items.filter { $0.id != id })
    }

    private func commit(_ newItems: [Item]) throws {
        try store.save(newItems)
        items = newItems
        dataDidChange()
    }

    /// データが変わったあとの後処理はここ 1 か所に集める（Intent 側に書かない）
    private func dataDidChange() {
        WidgetCenter.shared.reloadAllTimelines()
    }
}
