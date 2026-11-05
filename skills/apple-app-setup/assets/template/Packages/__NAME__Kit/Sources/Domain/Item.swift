import Foundation

public struct Item: Identifiable, Hashable, Codable, Sendable {
    public var id: UUID
    public var title: String
    public var dueDate: Date?

    public init(id: UUID = UUID(), title: String, dueDate: Date? = nil) {
        self.id = id
        self.title = title
        self.dueDate = dueDate
    }
}

extension [Item] {
    /// 期限のあるものを期限の近い順に、期限の無いものはその後ろに並べる。
    public func sortedByDueDate() -> [Item] {
        sorted { lhs, rhs in
            switch (lhs.dueDate, rhs.dueDate) {
            case let (l?, r?): l < r
            case (.some, nil): true
            case (nil, .some): false
            case (nil, nil): lhs.title.localizedStandardCompare(rhs.title) == .orderedAscending
            }
        }
    }
}
