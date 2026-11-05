import XCTest

final class __NAME__UITests: XCTestCase {
    @MainActor
    func testLaunchShowsTheList() {
        let app = XCUIApplication()
        // accessibility の文言で要素を引くので言語を固定する
        app.launchArguments += ["-AppleLanguages", "(en)"]
        app.launch()

        XCTAssertTrue(app.navigationBars["Items"].waitForExistence(timeout: 5))
    }
}
