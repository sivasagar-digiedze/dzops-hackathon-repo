import { useState } from "react";
import { sendChatMessage } from "../api/chat.api";

function ChatbotPage() {
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([
    { sender: "bot", text: "Hello! I can help with your cloud and ticket queries." },
  ]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const userText = chatInput.trim();
    if (!userText) return;
    const userMessage = { sender: "user", text: userText };
    const botMessage = await sendChatMessage(userText);
    setChatMessages((prev) => [...prev, userMessage, botMessage]);
    setChatInput("");
  };

  return (
    <section className="card">
      <h2>Chatbot</h2>
      <div className="chat-window">
        {chatMessages.map((msg, index) => (
          <p key={`${msg.sender}-${index}`} className={`chat-message ${msg.sender}`}>
            <strong>{msg.sender === "bot" ? "Bot" : "You"}:</strong> {msg.text}
          </p>
        ))}
      </div>
      <form className="chat-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          placeholder="Ask about organizations, clouds, or tickets..."
        />
        <button type="submit">Send</button>
      </form>
    </section>
  );
}

export default ChatbotPage;
