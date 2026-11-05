import AppIntents
import AppIntentsKit
import Persistence
import SwiftUI
import WidgetKit
import WidgetUI

@main
struct __NAME__WidgetBundle: WidgetBundle {
    init() {
        // アプリでの登録はこのプロセスに引き継がれない。拡張でも Intent や Query を解決するなら登録が要る
        MainActor.assumeIsolated {
            let service = ItemService(store: JSONFileItemStore.shared(appGroup: AppGroup.identifier))
            AppDependencyManager.shared.add(dependency: service)
        }
    }

    var body: some Widget {
        ItemsWidget()
    }
}
