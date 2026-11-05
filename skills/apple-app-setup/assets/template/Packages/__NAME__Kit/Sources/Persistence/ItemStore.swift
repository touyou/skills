import Domain
import Foundation

public enum AppGroup {
    /// アプリと拡張で同じ値を使う。entitlements の App Group と一致させる
    public static let identifier = "__APP_GROUP__"
}

public protocol ItemStore: Sendable {
    func load() throws -> [Item]
    func save(_ items: [Item]) throws
}

public struct JSONFileItemStore: ItemStore {
    public let url: URL

    public init(url: URL) {
        self.url = url
    }

    /// App Group のコンテナに置く。entitlement が無い環境（テストなど）では Application Support に落ちる
    public static func shared(appGroup: String) -> JSONFileItemStore {
        let base = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroup)
            ?? URL.applicationSupportDirectory
        return JSONFileItemStore(url: base.appending(path: "items.json"))
    }

    public func load() throws -> [Item] {
        guard FileManager.default.fileExists(atPath: url.path(percentEncoded: false)) else { return [] }
        return try JSONDecoder().decode([Item].self, from: Data(contentsOf: url))
    }

    public func save(_ items: [Item]) throws {
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try JSONEncoder().encode(items).write(to: url, options: .atomic)
    }
}
