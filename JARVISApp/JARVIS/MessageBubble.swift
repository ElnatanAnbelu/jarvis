import SwiftUI

struct MessageBubble: View {
    let message: Message

    var isUser: Bool { message.role == "user" }

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            if isUser { Spacer(minLength: 40) }

            VStack(alignment: isUser ? .trailing : .leading, spacing: 4) {
                if !isUser {
                    Text(message.agentLabel)
                        .font(.system(size: 8, weight: .bold, design: .monospaced))
                        .foregroundColor(message.agentColor)
                        .tracking(3)
                        .padding(.leading, 4)
                }

                Text(message.content)
                    .font(.system(size: 13, weight: .regular, design: .monospaced))
                    .foregroundColor(isUser ? Color(hex: "E0E0E0") : .white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(isUser
                                ? Color(hex: "0A1628").opacity(0.9)
                                : Color(hex: "050D1A").opacity(0.95))
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(
                                        isUser
                                            ? Color(hex: "FFFFFF").opacity(0.08)
                                            : message.agentColor.opacity(0.25),
                                        lineWidth: 0.8
                                    )
                            )
                    )
                    .shadow(color: isUser ? .clear : message.agentColor.opacity(0.1), radius: 8)
            }

            if !isUser { Spacer(minLength: 40) }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 3)
    }
}
