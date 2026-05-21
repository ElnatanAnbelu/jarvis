// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "JARVIS",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "JARVIS",
            path: "JARVIS",
            swiftSettings: [.unsafeFlags(["-parse-as-library"])]
        )
    ]
)
