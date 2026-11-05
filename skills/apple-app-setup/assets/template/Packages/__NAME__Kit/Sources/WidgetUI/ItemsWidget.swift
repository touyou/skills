import Domain
import Persistence
import SwiftUI
import WidgetKit

struct ItemsEntry: TimelineEntry {
    let date: Date
    let items: [Item]
}

struct ItemsProvider: TimelineProvider {
    func placeholder(in context: Context) -> ItemsEntry {
        ItemsEntry(date: .now, items: [])
    }

    func getSnapshot(in context: Context, completion: @escaping (ItemsEntry) -> Void) {
        completion(currentEntry())
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ItemsEntry>) -> Void) {
        // 更新はアプリ側の ItemService が reloadAllTimelines で知らせる
        completion(Timeline(entries: [currentEntry()], policy: .never))
    }

    private func currentEntry() -> ItemsEntry {
        let items = (try? JSONFileItemStore.shared(appGroup: AppGroup.identifier).load()) ?? []
        return ItemsEntry(date: .now, items: items.sortedByDueDate())
    }
}

public struct ItemsWidget: Widget {
    public init() {}

    public var body: some WidgetConfiguration {
        StaticConfiguration(kind: "ItemsWidget", provider: ItemsProvider()) { entry in
            ItemsWidgetView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName(Text(.copy("⟦Items⟧")))
        .description(Text(.copy("⟦Shows the items due soonest.⟧")))
    }
}

struct ItemsWidgetView: View {
    let entry: ItemsEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(.copy("⟦Items⟧"))
                .font(.headline)
            if entry.items.isEmpty {
                Text(.copy("⟦No Items⟧"))
                    .foregroundStyle(.secondary)
            } else {
                ForEach(entry.items.prefix(3)) { item in
                    Text(verbatim: item.title)
                        .lineLimit(1)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}
