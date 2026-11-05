import Foundation

extension LocalizedStringResource {
    /// このパッケージのカタログから引く。素の Text("…") は Bundle.main を引くので、パッケージのカタログに届かない
    static func copy(_ key: String.LocalizationValue) -> LocalizedStringResource {
        LocalizedStringResource(key, bundle: .atURL(Bundle.module.bundleURL))
    }
}
