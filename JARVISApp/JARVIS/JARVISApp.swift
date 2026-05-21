import SwiftUI

@main
struct JARVISApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings { EmptyView() }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var popover: NSPopover?
    var backendProcess: Process?

    func applicationDidFinishLaunching(_ notification: Notification) {
        startBackend()
        setupMenuBar()
        registerHotkey()

        // Wait for backend then greet
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            self.sendInit()
        }
    }

    func startBackend() {
        let jarvisDir = URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("jarvis")
        let venvPython = jarvisDir.appendingPathComponent("venv/bin/python3").path
        let serverScript = jarvisDir.appendingPathComponent("ui/server.py").path

        let process = Process()
        process.executableURL = URL(fileURLWithPath: venvPython)
        process.arguments = [serverScript]
        process.currentDirectoryURL = jarvisDir
        process.environment = ProcessInfo.processInfo.environment

        do {
            try process.run()
            backendProcess = process
        } catch {
            print("Failed to start backend: \(error)")
        }
    }

    func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem?.button {
            button.image = NSImage(systemSymbolName: "brain.head.profile", accessibilityDescription: "JARVIS")
            button.action = #selector(togglePopover)
            button.target = self
        }

        popover = NSPopover()
        popover?.contentSize = NSSize(width: 480, height: 700)
        popover?.behavior = .transient
        popover?.contentViewController = NSHostingController(rootView: ContentView())
    }

    @objc func togglePopover() {
        guard let button = statusItem?.button, let popover = popover else { return }
        if popover.isShown {
            popover.performClose(nil)
        } else {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            popover.contentViewController?.view.window?.makeKey()
        }
    }

    func registerHotkey() {
        NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            // Cmd + Shift + J
            if event.modifierFlags.contains([.command, .shift]) && event.keyCode == 38 {
                DispatchQueue.main.async { self?.togglePopover() }
            }
        }
    }

    func sendInit() {
        guard let url = URL(string: "http://localhost:8080/api/chat") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(["message": "__init__"])
        URLSession.shared.dataTask(with: request).resume()
    }

    func applicationWillTerminate(_ notification: Notification) {
        backendProcess?.terminate()
    }
}
