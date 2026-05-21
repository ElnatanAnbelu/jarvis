import SwiftUI

struct Message: Identifiable, Equatable {
    let id = UUID()
    let role: String      // "user", "jarvis", "friday", "veronica", "karen", "system"
    let content: String
    let timestamp: Date

    var agentColor: Color {
        switch role.uppercased() {
        case "JARVIS":   return Color(hex: "00D4FF")
        case "FRIDAY":   return Color(hex: "A064FF")
        case "VERONICA": return Color(hex: "00FF9F")
        case "KAREN":    return Color(hex: "FFB450")
        case "USER":     return Color(hex: "FFFFFF")
        default:         return Color(hex: "888888")
        }
    }

    var agentLabel: String {
        role.uppercased()
    }
}

struct ContentCard: Identifiable {
    let id = UUID()
    let type: CardType
    let title: String
    let subtitle: String
    let body: String
    let timestamp: Date

    enum CardType {
        case email, message, calendar, image, news, weather, task, project
    }
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255
        let g = Double((int >> 8) & 0xFF) / 255
        let b = Double(int & 0xFF) / 255
        self.init(red: r, green: g, blue: b)
    }
}
