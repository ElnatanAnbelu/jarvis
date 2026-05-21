import SwiftUI

struct ContentView: View {
    @StateObject private var vm = JARVISViewModel()
    @State private var showRing = true

    var body: some View {
        ZStack {
            // Background
            Color(hex: "020914")
                .ignoresSafeArea()

            // Grid overlay
            GridPattern()
                .opacity(0.04)
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                HUDHeader()

                // Ring
                if showRing {
                    HUDRingView(
                        speaker: vm.currentSpeaker,
                        isThinking: vm.isThinking,
                        pulse: vm.ringPulse
                    )
                    .frame(height: 180)
                    .padding(.vertical, 8)
                }

                // Messages
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(vm.messages) { msg in
                                MessageBubble(message: msg)
                                    .id(msg.id)
                            }

                            if vm.isThinking {
                                ThinkingIndicator(speaker: vm.currentSpeaker)
                                    .id("thinking")
                            }
                        }
                        .padding(.vertical, 8)
                    }
                    .onChange(of: vm.messages.count) { _ in
                        if let last = vm.messages.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                    .onChange(of: vm.isThinking) { _ in
                        if vm.isThinking {
                            withAnimation { proxy.scrollTo("thinking", anchor: .bottom) }
                        }
                    }
                }

                Divider()
                    .background(Color(hex: "00D4FF").opacity(0.15))

                // Input
                InputBar(vm: vm)
            }
        }
        .frame(width: 480, height: 700)
        .onAppear {
            // Collapse ring when there are messages
        }
    }
}

struct HUDHeader: View {
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("J.A.R.V.I.S")
                    .font(.system(size: 13, weight: .bold, design: .monospaced))
                    .foregroundColor(Color(hex: "00D4FF"))
                    .tracking(6)
                Text("JUST A RATHER VERY INTELLIGENT SYSTEM")
                    .font(.system(size: 6, weight: .regular, design: .monospaced))
                    .foregroundColor(Color(hex: "00D4FF").opacity(0.35))
                    .tracking(3)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(Date(), style: .time)
                    .font(.system(size: 11, weight: .regular, design: .monospaced))
                    .foregroundColor(Color(hex: "00D4FF").opacity(0.6))
                Text("ONLINE")
                    .font(.system(size: 7, weight: .bold, design: .monospaced))
                    .foregroundColor(Color(hex: "00FF9F").opacity(0.8))
                    .tracking(3)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color(hex: "020914"))
        .overlay(
            Rectangle()
                .frame(height: 0.5)
                .foregroundColor(Color(hex: "00D4FF").opacity(0.2)),
            alignment: .bottom
        )
    }
}

struct ThinkingIndicator: View {
    let speaker: String
    @State private var dotCount = 0

    var agentColor: Color {
        switch speaker.uppercased() {
        case "FRIDAY":   return Color(hex: "A064FF")
        case "VERONICA": return Color(hex: "00FF9F")
        case "KAREN":    return Color(hex: "FFB450")
        default:         return Color(hex: "00D4FF")
        }
    }

    var body: some View {
        HStack(spacing: 0) {
            Text(String(repeating: "●", count: dotCount + 1))
                .font(.system(size: 10, design: .monospaced))
                .foregroundColor(agentColor.opacity(0.6))
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color(hex: "050D1A").opacity(0.95))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(agentColor.opacity(0.2), lineWidth: 0.8)
                        )
                )
                .padding(.horizontal, 12)
                .padding(.vertical, 3)
            Spacer()
        }
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { t in
                dotCount = (dotCount + 1) % 3
            }
        }
    }
}

struct InputBar: View {
    @ObservedObject var vm: JARVISViewModel
    @FocusState private var focused: Bool

    var body: some View {
        HStack(spacing: 8) {
            TextField("", text: $vm.inputText, prompt:
                Text("Ask JARVIS...")
                    .foregroundColor(Color(hex: "FFFFFF").opacity(0.2))
                    .font(.system(size: 13, design: .monospaced))
            )
            .font(.system(size: 13, design: .monospaced))
            .foregroundColor(.white)
            .focused($focused)
            .onSubmit { vm.send(vm.inputText) }
            .textFieldStyle(.plain)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color(hex: "050D1A"))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color(hex: "00D4FF").opacity(focused ? 0.4 : 0.15), lineWidth: 0.8)
                    )
            )

            Button(action: { vm.send(vm.inputText) }) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(Color(hex: "00D4FF"))
                    .frame(width: 32, height: 32)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(Color(hex: "00D4FF").opacity(0.1))
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(Color(hex: "00D4FF").opacity(0.3), lineWidth: 0.8)
                            )
                    )
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(Color(hex: "020914"))
        .onAppear { focused = true }
    }
}

struct GridPattern: View {
    var body: some View {
        Canvas { context, size in
            let spacing: CGFloat = 30
            var x: CGFloat = 0
            while x <= size.width {
                context.stroke(Path { p in p.move(to: CGPoint(x: x, y: 0)); p.addLine(to: CGPoint(x: x, y: size.height)) },
                               with: .color(.white), lineWidth: 0.3)
                x += spacing
            }
            var y: CGFloat = 0
            while y <= size.height {
                context.stroke(Path { p in p.move(to: CGPoint(x: 0, y: y)); p.addLine(to: CGPoint(x: size.width, y: y)) },
                               with: .color(.white), lineWidth: 0.3)
                y += spacing
            }
        }
    }
}
