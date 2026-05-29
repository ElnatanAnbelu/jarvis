import SwiftUI

struct HUDRingView: View {
    let speaker: String
    let isThinking: Bool
    let pulse: Bool

    var agentColor: Color {
        switch speaker.uppercased() {
        case "FRIDAY":   return Color(hex: "FF6A00")
        case "VERONICA": return Color(hex: "00FF9F")
        case "KAREN":    return Color(hex: "FFB450")
        default:         return Color(hex: "00E5FF")
        }
    }

    var body: some View {
        ZStack {
            // Outer glow ring
            Circle()
                .stroke(agentColor.opacity(0.15), lineWidth: 1)
                .frame(width: 160, height: 160)
                .scaleEffect(pulse ? 1.08 : 1.0)

            // Main ring
            Circle()
                .stroke(agentColor.opacity(0.4), lineWidth: 1.5)
                .frame(width: 130, height: 130)

            // Inner spinning arc
            Circle()
                .trim(from: 0, to: isThinking ? 0.7 : 0.25)
                .stroke(agentColor, style: StrokeStyle(lineWidth: 2, lineCap: .round))
                .frame(width: 110, height: 110)
                .rotationEffect(.degrees(isThinking ? 360 : 0))
                .animation(isThinking ? .linear(duration: 1.2).repeatForever(autoreverses: false) : .easeInOut(duration: 1.0), value: isThinking)

            // Inner dot ring
            ForEach(0..<12, id: \.self) { i in
                Circle()
                    .fill(agentColor.opacity(i % 3 == 0 ? 0.8 : 0.3))
                    .frame(width: i % 3 == 0 ? 4 : 2.5, height: i % 3 == 0 ? 4 : 2.5)
                    .offset(y: -52)
                    .rotationEffect(.degrees(Double(i) * 30))
            }

            // Center
            VStack(spacing: 2) {
                Text(speaker.uppercased())
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .foregroundColor(agentColor)
                    .tracking(4)
                Text(isThinking ? "PROCESSING" : "ONLINE")
                    .font(.system(size: 6, weight: .regular, design: .monospaced))
                    .foregroundColor(agentColor.opacity(0.5))
                    .tracking(3)
            }
        }
        .animation(.easeInOut(duration: 0.8), value: pulse)
        .animation(.easeInOut(duration: 0.4), value: speaker)
    }
}
