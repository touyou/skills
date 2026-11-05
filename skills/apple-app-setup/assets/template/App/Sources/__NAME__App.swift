import AppIntents
import AppIntentsKit
import AppUI
import Persistence
import SwiftUI

@main
struct __NAME__App: App {
    @State private var service: ItemService

    init() {
        let service = ItemService(store: JSONFileItemStore.shared(appGroup: AppGroup.identifier))
        _service = State(initialValue: service)
        // @Dependency の登録はプロセスごと。拡張では拡張の側で別に登録する
        AppDependencyManager.shared.add(dependency: service)
    }

    var body: some Scene {
        WindowGroup {
            ItemListView()
                .environment(service)
        }
    }
}
