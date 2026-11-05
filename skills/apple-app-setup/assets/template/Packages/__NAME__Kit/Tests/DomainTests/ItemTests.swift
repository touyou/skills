import Domain
import Foundation
import Testing

struct ItemTests {
    @Test func itemsWithADueDateComeFirstInDateOrder() {
        let later = Item(title: "later", dueDate: Date(timeIntervalSince1970: 200))
        let sooner = Item(title: "sooner", dueDate: Date(timeIntervalSince1970: 100))
        let undated = Item(title: "undated")

        #expect([undated, later, sooner].sortedByDueDate().map(\.title) == ["sooner", "later", "undated"])
    }
}
