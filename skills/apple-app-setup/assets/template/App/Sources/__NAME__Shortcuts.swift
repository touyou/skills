import AppIntents
import AppIntentsKit

// パッケージに置くと App Shortcut が 0 件になる（ビルドは緑のまま）。必ずアプリのターゲットに置く
struct __NAME__Shortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AddItemIntent(),
            phrases: [
                "Add an item in \(.applicationName)",
                "New item in \(.applicationName)"
            ],
            shortTitle: "Add Item",
            systemImageName: "plus"
        )
        AppShortcut(
            intent: GetItemCountIntent(),
            phrases: [
                "How many items are in \(.applicationName)"
            ],
            shortTitle: "Item Count",
            systemImageName: "number"
        )
    }
}
