import XCTest

final class __NAME__UITests: XCTestCase {
    @MainActor
    func testLaunchShowsTheList() {
        let app = XCUIApplication()
        app.launch()

        // 文言は言語で変わるので識別子で引く
        XCTAssertTrue(app.descendants(matching: .any)["itemList"].waitForExistence(timeout: 5))
    }
}
