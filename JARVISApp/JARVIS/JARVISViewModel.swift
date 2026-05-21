import SwiftUI
import Combine
import AVFoundation
import Speech

@MainActor
class JARVISViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var inputText: String = ""
    @Published var isThinking: Bool = false
    @Published var currentSpeaker: String = "JARVIS"
    @Published var isListening: Bool = false
    @Published var ringPulse: Bool = false

    private var streamTask: URLSessionDataTask?
    private let baseURL = "http://localhost:8080"

    init() {
        // Pulse ring animation
        Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                withAnimation(.easeInOut(duration: 0.8)) {
                    self?.ringPulse.toggle()
                }
            }
        }
    }

    func send(_ text: String) {
        guard !text.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        let userMsg = Message(role: "user", content: text, timestamp: Date())
        messages.append(userMsg)
        inputText = ""
        isThinking = true

        // Cancel any existing stream
        streamTask?.cancel()
        streamTask = nil

        streamResponse(text)
    }

    private func streamResponse(_ text: String) {
        guard let encoded = text.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "\(baseURL)/api/stream?message=\(encoded)") else { return }

        var accumulated = ""
        var agent = "JARVIS"
        var messageAdded = false

        let session = URLSession(configuration: .default)
        let task = session.dataTask(with: url) { [weak self] data, _, error in
            guard let data = data, error == nil else { return }
            let raw = String(data: data, encoding: .utf8) ?? ""
            let lines = raw.components(separatedBy: "\n")

            for line in lines {
                guard line.hasPrefix("data: ") else { continue }
                let jsonStr = String(line.dropFirst(6))
                guard let jsonData = jsonStr.data(using: .utf8),
                      let obj = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
                      let type = obj["type"] as? String else { continue }

                Task { @MainActor [weak self] in
                    guard let self = self else { return }
                    switch type {
                    case "thinking":
                        self.isThinking = true
                    case "speaker":
                        agent = (obj["name"] as? String) ?? "JARVIS"
                        self.currentSpeaker = agent
                    case "text":
                        let chunk = (obj["chunk"] as? String) ?? ""
                        accumulated += chunk
                        self.isThinking = false
                        if !messageAdded {
                            self.messages.append(Message(role: agent.lowercased(), content: accumulated, timestamp: Date()))
                            messageAdded = true
                        } else if var last = self.messages.last, last.role == agent.lowercased() {
                            self.messages[self.messages.count - 1] = Message(role: agent.lowercased(), content: accumulated, timestamp: last.timestamp)
                        }
                    case "done":
                        self.isThinking = false
                    default: break
                    }
                }
            }
        }
        streamTask = task
        task.resume()
    }
}
