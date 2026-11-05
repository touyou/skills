import AppIntents
import Foundation

public struct AddItemIntent: AppIntent {
    public static let title: LocalizedStringResource = "Add Item"
    public static let description = IntentDescription("Adds a new item.")
    public static var supportedModes: IntentModes { .background }

    /// 書き込む Intent と App Shortcut に登録する Intent はアプリのプロセスに固定する
    public static var allowedExecutionTargets: IntentExecutionTargets { [.main] }

    /// Shortcuts の編集画面に出るのはここに載せたパラメータだけ
    public static var parameterSummary: some ParameterSummary {
        Summary("Add \(\.$title)") {
            \.$dueDate
        }
    }

    @Parameter(title: "Title")
    public var title: String

    @Parameter(title: "Due Date")
    public var dueDate: Date?

    @Dependency private var service: ItemService

    public init() {}

    public init(title: String, dueDate: Date? = nil) {
        self.title = title
        self.dueDate = dueDate
    }

    @MainActor
    public func perform() async throws -> some IntentResult & ReturnsValue<ItemEntity> & ProvidesDialog {
        let item = try service.add(title: title, dueDate: dueDate)
        return .result(value: ItemEntity(item: item), dialog: "Added \(title).")
    }
}

public struct GetItemCountIntent: AppIntent {
    public static let title: LocalizedStringResource = "Get Item Count"
    public static let description = IntentDescription("Tells how many items there are.")
    public static var supportedModes: IntentModes { .background }
    public static var allowedExecutionTargets: IntentExecutionTargets { [.main] }

    @Dependency private var service: ItemService

    public init() {}

    @MainActor
    public func perform() async throws -> some IntentResult & ReturnsValue<Int> & ProvidesDialog {
        let count = service.items.count
        return .result(value: count, dialog: "\(count) items.")
    }
}
