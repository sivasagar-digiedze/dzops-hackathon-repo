import { requestJson } from "./httpClient";

export const chatApi = {
  id: "chatbot",
  method: "POST",
  endpoint: "/api/chat",
  title: "Chatbot Query",
};

export const sendChatMessage = async (message) => {
  try {
    return await requestJson(chatApi.endpoint, {
      method: chatApi.method,
      body: JSON.stringify({ message }),
    });
  } catch {
    return {
      sender: "bot",
      text: `Received: "${message}". I will check cloud accounts and ticket activity for that request.`,
    };
  }
};
