import AppIntents
import Domain
import Foundation

public struct ItemEntity: AppEntity {
    public static let typeDisplayRepresentation: TypeDisplayRepresentation = "⟦Item⟧"

    public static var defaultQuery: ItemQuery {
        ItemQuery()
    }

    public let id: UUID

    @Property(title: "⟦Title⟧")
    public var title: String

    @Property(title: "⟦Due Date⟧")
    public var dueDate: Date?

    public var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(title)")
    }

    public init(item: Item) {
        self.id = item.id
        self.title = item.title
        self.dueDate = item.dueDate
    }
}

public struct ItemQuery: EntityQuery {
    @Dependency private var service: ItemService

    public init() {}

    @MainActor
    public func entities(for identifiers: [ItemEntity.ID]) async throws -> [ItemEntity] {
        identifiers.compactMap { service.item(id: $0) }.map(ItemEntity.init(item:))
    }

    @MainActor
    public func suggestedEntities() async throws -> [ItemEntity] {
        service.items.map(ItemEntity.init(item:))
    }
}
