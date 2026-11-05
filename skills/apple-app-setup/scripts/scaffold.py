#!/usr/bin/env python3
"""Apple プラットフォームのアプリのひな形を書き出す。

assets/template/ を複製してプレースホルダを置き換え、platform に依存する
project.yml と Package.swift はここで組み立てる。標準ライブラリだけで動く。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "template"
# ひな形の文言は ⟦英語⟧ で書き、--source-language ja のときはこの表で日本語にする（フレーズもソース言語で書く必要がある）
JA_STRINGS = SKILL_DIR / "assets" / "strings-ja.json"

PLATFORMS = {
    # key: (XcodeGen の destination, SwiftPM の platform, 表示名)
    "ios": ("iOS", "iOS", "iOS / iPadOS"),
    "macos": ("macOS", "macOS", "macOS"),
    "visionos": ("visionOS", "visionOS", "visionOS"),
}

RESERVED_NAMES = {"App", "Widget", "Domain", "Persistence", "AppIntentsKit", "AppUI", "WidgetUI"}

# ファイル名を変えて置くもの（ドットファイルは assets に置くと見落とされやすい）
RENAMES = {"gitignore": ".gitignore", "swiftlint.yml": ".swiftlint.yml"}

WIDGET_ONLY = ("Widget/", "Packages/__NAME__Kit/Sources/WidgetUI/")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", required=True, help="Swift の型名にも使う英名（例: CsirtCalendar）")
    p.add_argument("--display-name", help="ホーム画面の表示名（省略時は --name）")
    p.add_argument("--bundle-id", required=True, help="例: dev.touyou.csirtcalendar")
    p.add_argument("--team", default="", help="DEVELOPMENT_TEAM。空でも書き出せるが、署名が要るテストは動かない")
    p.add_argument("--platforms", default="ios", help="ios,macos,visionos から選ぶ（カンマ区切り）")
    p.add_argument("--min-os", default="27.0", help="全プラットフォーム共通の最低バージョン")
    p.add_argument("--source-language", default="en", choices=["en", "ja"], help="String Catalog のソース言語")
    p.add_argument("--one-liner", default="", help="アプリを 1 文で（AGENTS.md・README・PLAN に入る）")
    p.add_argument("--category", default="public.app-category.productivity", help="LSApplicationCategoryType")
    p.add_argument("--widget", action=argparse.BooleanOptionalAction, default=True, help="ウィジェット拡張を入れる")
    p.add_argument("--network", action="store_true", help="macOS のサンドボックスで外向きの通信を許す")
    p.add_argument("--icloud", action="store_true", help="CloudKit のコンテナ iCloud.<bundle id> を entitlements に足す")
    p.add_argument("--out", required=True, help="書き出し先（存在しない、または空のディレクトリ）")
    args = p.parse_args(argv)

    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", args.name):
        p.error("--name は大文字で始まる英数字にする（Swift の型名とターゲット名に使う）")
    if not re.fullmatch(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+", args.bundle_id):
        p.error("--bundle-id は逆ドメイン形式にする")
    if not re.fullmatch(r"\d+\.\d+", args.min_os):
        p.error("--min-os は 27.0 のように書く")
    if tuple(int(x) for x in args.min_os.split(".")) < (27, 0):
        p.error("--min-os は 27.0 以上にする（ひな形が IntentExecutionTargets など 27 の API を使う）")
    if args.name in RESERVED_NAMES:
        p.error(f"--name に {args.name} は使えない（パッケージのモジュール名と衝突する）")
    platforms = [s.strip().lower() for s in args.platforms.split(",") if s.strip()]
    unknown = [s for s in platforms if s not in PLATFORMS]
    if unknown or not platforms:
        p.error(f"--platforms に使えるのは {', '.join(PLATFORMS)}")
    args.platforms = platforms
    args.display_name = args.display_name or args.name
    return args


def yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def entitlements(args: argparse.Namespace, indent: str, *, icloud: bool) -> list[str]:
    lines = [f"{indent}com.apple.security.application-groups:", f"{indent}  - {app_group(args)}"]
    if icloud:
        # 同期の通知（プッシュとバックグラウンドモード）は Xcode の Signing & Capabilities で足す
        lines += [
            f"{indent}com.apple.developer.icloud-services:",
            f"{indent}  - CloudKit",
            f"{indent}com.apple.developer.icloud-container-identifiers:",
            f"{indent}  - iCloud.{args.bundle_id}",
        ]
    return lines


def app_group(args: argparse.Namespace) -> str:
    return f"group.{args.bundle_id}"


def project_yml(args: argparse.Namespace) -> str:
    n = args.name
    dests = [PLATFORMS[p][0] for p in args.platforms]
    dest_list = "[" + ", ".join(dests) + "]"
    prefix = args.bundle_id.rsplit(".", 1)[0]
    deploy = "\n".join(f'    {d}: "{args.min_os}"' for d in dests)

    app_settings = [
        f"        PRODUCT_BUNDLE_IDENTIFIER: {args.bundle_id}",
        "        GENERATE_INFOPLIST_FILE: YES",
        f"        INFOPLIST_KEY_CFBundleDisplayName: {yaml_str(args.display_name)}",
        f"        INFOPLIST_KEY_LSApplicationCategoryType: {yaml_str(args.category)}",
        "        INFOPLIST_KEY_ITSAppUsesNonExemptEncryption: NO",
        "        ASSETCATALOG_COMPILER_APPICON_NAME: AppIcon",
        "        ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME: AccentColor",
    ]
    if "ios" in args.platforms or "visionos" in args.platforms:
        app_settings += [
            "        INFOPLIST_KEY_UIApplicationSceneManifest_Generation: YES",
            "        INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents: YES",
        ]
    if "ios" in args.platforms:
        family = "1,2,7" if "visionos" in args.platforms else "1,2"
        app_settings += [
            f"        TARGETED_DEVICE_FAMILY: \"{family}\"",
            "        # 無いと iOS 27 ではアップロードが ITMS-90870 で弾かれる",
            "        INFOPLIST_KEY_UILaunchScreen_Generation: YES",
            "        # iPad は 4 方向すべて（リサイズ前提。UIRequiresFullScreen は使わない）",
            "        INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone: \"UIInterfaceOrientationPortrait UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight\"",
            "        INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad: \"UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight\"",
        ]
    if "macos" in args.platforms:
        app_settings += ["        ENABLE_APP_SANDBOX: YES", "        ENABLE_HARDENED_RUNTIME: YES"]
        if args.network:
            app_settings.append("        ENABLE_OUTGOING_NETWORK_CONNECTIONS: YES")

    out = [
        f"name: {n}",
        "options:",
        f"  bundleIdPrefix: {prefix}",
        "  deploymentTarget:",
        deploy,
        f"  developmentLanguage: {args.source_language}",
        "  createIntermediateGroups: true",
        "packages:",
        f"  {n}Kit:",
        f"    path: Packages/{n}Kit",
        "settings:",
        "  base:",
        f"    DEVELOPMENT_TEAM: {yaml_str(args.team)}",
        "    CODE_SIGN_STYLE: Automatic",
        '    SWIFT_VERSION: "6.0"',
        "    SWIFT_EMIT_LOC_STRINGS: YES",
        "    LOCALIZATION_PREFERS_STRING_CATALOGS: YES",
        "    ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS: YES",
        "    ENABLE_USER_SCRIPT_SANDBOXING: YES",
        "    DEAD_CODE_STRIPPING: YES",
        '    MARKETING_VERSION: "0.1.0"',
        '    CURRENT_PROJECT_VERSION: "1"',
        "targets:",
        f"  {n}:",
        "    type: application",
        f"    supportedDestinations: {dest_list}",
        "    sources:",
        "      - App",
        "    entitlements:",
        f"      path: App/{n}.entitlements",
        "      properties:",
        *entitlements(args, "        ", icloud=args.icloud),
        "    dependencies:",
    ]
    for product in ("AppUI", "AppIntentsKit", "Persistence"):
        out += [f"      - package: {n}Kit", f"        product: {product}"]
    if args.widget:
        out.append(f"      - target: {n}Widget")
    out += ["    settings:", "      base:", *app_settings]

    if args.widget:
        out += [
            f"  {n}Widget:",
            "    type: app-extension",
            f"    supportedDestinations: {dest_list}",
            "    sources:",
            "      - Widget",
            "    info:",
            "      path: Widget/Info.plist",
            "      properties:",
            "        NSExtension:",
            "          NSExtensionPointIdentifier: com.apple.widgetkit-extension",
            "    entitlements:",
            f"      path: Widget/{n}Widget.entitlements",
            "      properties:",
            *entitlements(args, "        ", icloud=False),
            "    dependencies:",
        ]
        for product in ("WidgetUI", "AppIntentsKit", "Persistence"):
            out += [f"      - package: {n}Kit", f"        product: {product}"]
        out += [
            "    settings:",
            "      base:",
            f"        PRODUCT_BUNDLE_IDENTIFIER: {args.bundle_id}.widget",
            "        GENERATE_INFOPLIST_FILE: YES",
            f"        INFOPLIST_KEY_CFBundleDisplayName: {yaml_str(args.display_name)}",
            "        SKIP_INSTALL: YES",
        ]
        if "macos" in args.platforms:
            out += ["        ENABLE_APP_SANDBOX: YES"]

    out += [
        f"  {n}UITests:",
        "    type: bundle.ui-testing",
        f"    supportedDestinations: {dest_list}",
        "    sources:",
        "      - AppUITests",
        "    dependencies:",
        f"      - target: {n}",
        "    settings:",
        "      base:",
        f"        PRODUCT_BUNDLE_IDENTIFIER: {args.bundle_id}.uitests",
        "        GENERATE_INFOPLIST_FILE: YES",
        f"        TEST_TARGET_NAME: {n}",
        "schemes:",
        f"  {n}:",
        "    build:",
        "      targets:",
        f"        {n}: all",
        "    test:",
        "      config: Debug",
        "      # パッケージのテストもここに並べる。足さないとコンパイルできなくなっても赤くならない",
        "      targets:",
        f"        - {n}UITests",
        f"        - package: {n}Kit/DomainTests",
        f"        - package: {n}Kit/AppIntentsKitTests",
        "    archive:",
        "      config: Release",
    ]
    return "\n".join(out) + "\n"


def package_swift(args: argparse.Namespace) -> str:
    n = args.name
    # SwiftPM の platform はメジャーまで。27.3 などポイントリリースの API は @available で囲む
    major = args.min_os.split(".")[0]
    # swift test は Mac の上で macOS 向けに回るので、macOS を対象にしなくても macOS の下限は要る
    names = list(dict.fromkeys([*(PLATFORMS[p][1] for p in args.platforms), "macOS"]))
    platforms = ", ".join(f".{name}(.v{major})" for name in names)
    products = ["Domain", "Persistence", "AppIntentsKit", "AppUI"] + (["WidgetUI"] if args.widget else [])
    product_lines = ",\n".join(f'        .library(name: "{p}", targets: ["{p}"])' for p in products)
    targets = [
        '        .target(name: "Domain")',
        '        .target(name: "Persistence", dependencies: ["Domain"])',
        '        .target(name: "AppIntentsKit", dependencies: ["Domain", "Persistence"])',
        '        .target(name: "AppUI", dependencies: ["AppIntentsKit", "Domain"], resources: [.process("Resources")])',
    ]
    if args.widget:
        targets.append(
            '        .target(name: "WidgetUI", dependencies: ["Domain", "Persistence"], resources: [.process("Resources")])'
        )
    targets += [
        '        .testTarget(name: "DomainTests", dependencies: ["Domain"])',
        '        .testTarget(name: "AppIntentsKitTests", dependencies: ["AppIntentsKit", "Domain", "Persistence"])',
    ]
    target_lines = ",\n".join(targets)
    return f"""// swift-tools-version: 6.4
import PackageDescription

// ロジックはすべてこのパッケージに置く。アプリと拡張のターゲットはひな形だけ。
// AppIntentsPackage は宣言しない（静的リンクの間は不要で、配布版だけ App Intents が読まれなくなる）
let package = Package(
    name: "{n}Kit",
    defaultLocalization: "{args.source_language}",
    platforms: [{platforms}],
    products: [
{product_lines}
    ],
    targets: [
{target_lines}
    ]
)
"""


def build_commands(args: argparse.Namespace) -> str:
    n = args.name
    dests = [PLATFORMS[p][0] for p in args.platforms]
    lines = [f"xcodebuild build -scheme {n} -destination 'generic/platform={d}'" for d in dests]
    first = dests[0]
    lines.append(f"xcodebuild build -scheme {n} -configuration Release -destination 'generic/platform={first}'")
    sim = {"iOS": "iOS Simulator", "visionOS": "visionOS Simulator", "macOS": "macOS"}[first]
    lines.append(f"xcodebuild build-for-testing -scheme {n} -destination 'generic/platform={sim}'")
    return "\n".join(lines)


def replacements(args: argparse.Namespace) -> dict[str, str]:
    names = [PLATFORMS[p][2] for p in args.platforms]
    default_one_liner = (
        f"{args.display_name} のアプリ。" if args.source_language == "ja" else f"The {args.display_name} app."
    )
    return {
        "__NAME__": args.name,
        "__DISPLAY_NAME__": args.display_name,
        "__BUNDLE_ID__": args.bundle_id,
        "__APP_GROUP__": app_group(args),
        "__SOURCE_LANG__": args.source_language,
        "__MIN_OS__": args.min_os,
        "__PLATFORMS_TEXT__": " / ".join(names),
        "__ONE_LINER__": args.one_liner or default_one_liner,
        "__BUILD_COMMANDS__": build_commands(args),
    }


def substitute(text: str, table: dict[str, str]) -> str:
    for key, value in table.items():
        text = text.replace(key, value)
    return text


def widget_blocks(text: str, keep: bool) -> str:
    """⟪widget⟫…⟪/widget⟫ をウィジェットありなら印だけ外し、なしなら中身ごと消す"""
    if keep:
        return text.replace("⟪widget⟫", "").replace("⟪/widget⟫", "")
    return re.sub(r"⟪widget⟫.*?⟪/widget⟫", "", text, flags=re.S)


def missing_translations(language: str) -> list[str]:
    if language != "ja":
        return []
    strings = json.loads(JA_STRINGS.read_text(encoding="utf-8"))
    used = set()
    for src in TEMPLATE_DIR.rglob("*.swift"):
        used.update(re.findall(r"⟦(.*?)⟧", src.read_text(encoding="utf-8")))
    return sorted(used - strings.keys())


def localize(text: str, language: str) -> str:
    strings = json.loads(JA_STRINGS.read_text(encoding="utf-8")) if language == "ja" else {}

    def pick(match: re.Match[str]) -> str:
        source = match.group(1)
        if language == "ja" and source not in strings:
            raise KeyError(f"strings-ja.json に訳が無い: {source}")
        return strings.get(source, source)

    return re.sub(r"⟦(.*?)⟧", pick, text)


def copy_template(args: argparse.Namespace, out: Path, table: dict[str, str]) -> list[Path]:
    written: list[Path] = []
    for src in sorted(TEMPLATE_DIR.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE_DIR).as_posix()
        if not args.widget and rel.startswith(WIDGET_ONLY):
            continue
        rel = RENAMES.get(rel, rel)
        dest = out / substitute(rel, table)
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = substitute(src.read_text(encoding="utf-8"), table)
        text = localize(widget_blocks(text, args.widget), args.source_language)
        dest.write_text(text, encoding="utf-8")
        written.append(dest)
    return written


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    out = Path(os.path.expanduser(args.out)).resolve()
    if out.exists() and any(out.iterdir()):
        print(f"{out} は空ではない。上書きしないので、空のディレクトリを指定する", file=sys.stderr)
        return 1
    missing = missing_translations(args.source_language)
    if missing:
        print("strings-ja.json に訳が無い文言がある: " + ", ".join(missing), file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)

    table = replacements(args)
    written = copy_template(args, out, table)

    (out / "project.yml").write_text(project_yml(args), encoding="utf-8")
    pkg = out / "Packages" / f"{args.name}Kit" / "Package.swift"
    pkg.write_text(package_swift(args), encoding="utf-8")
    (out / "CLAUDE.md").symlink_to("AGENTS.md")
    written += [out / "project.yml", pkg, out / "CLAUDE.md"]

    print(f"{len(written)} ファイルを {out} に書き出した。次にやること:")
    print("  1. cd して `xcodegen generate`（.xcodeproj もコミットする）")
    print("  2. AGENTS.md の「コミット前に回すもの」を全部通す（Debug / Release / build-for-testing / swift test）")
    print("  3. git init → 最初のコミット → GitHub に作ったら `gh repo edit --delete-branch-on-merge`")
    print("  4. Item / AddItemIntent などのサンプルを、app-intents-design-session で決めた Intent に置き換える")
    if "visionos" in args.platforms:
        print("  ※ visionOS の組み合わせはまだビルドで確かめていない。アイコン（solidimagestack）とシーンの設定を見直す")
    if not args.team:
        print("  ※ --team が空。AppIntentsTesting など署名が要るテストは動かないので project.yml に入れる")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
