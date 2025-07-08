import React, { useState, useRef, useEffect } from "react";
import "./App.css";

type Message = {
  id: string;
  text: string;
  sender: "user" | "bot";
  timestamp: Date;
  type?: "error" | "normal";
};

type ChatResponse = {
  follow_up_question: string | null;
  triage_level?: string;
  error?: string;
} | { error: string } | null;

function App() {
  const [inputText, setInputText] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      text: "Hello! I'm your veterinary triage assistant. Please describe your pet's symptoms and I'll help assess the situation.",
      sender: "bot",
      timestamp: new Date(),
      type: "normal"
    }
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const addMessage = (text: string, sender: "user" | "bot", type: "error" | "normal" = "normal") => {
    const newMessage: Message = {
      id: Date.now().toString(),
      text,
      sender,
      timestamp: new Date(),
      type
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const handleClearChat = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      
      // Reset the chat to initial state
      setMessages([{
        id: "welcome",
        text: data.follow_up_question,
        sender: "bot",
        timestamp: new Date(),
        type: "normal"
      }]);
    } catch (err) {
      addMessage("Failed to clear chat. Please try again.", "bot", "error");
    }
    setLoading(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    const userMessage = inputText.trim();
    setInputText("");
    addMessage(userMessage, "user");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_answer: userMessage }),
      });
      const data: ChatResponse = await res.json();
      
      if (data && "error" in data) {
        addMessage(data.error || "An unknown error occurred", "bot", "error");
      } else if (data && data.follow_up_question) {
        let botResponse = data.follow_up_question;
        if (data.triage_level) {
          botResponse = `Triage Level: ${data.triage_level}\n\n${botResponse}`;
        }
        addMessage(botResponse, "bot");
      } else {
        addMessage("I received your message but couldn't generate a proper response. Please try again.", "bot", "error");
      }
    } catch (err) {
      addMessage("Sorry, I'm having trouble connecting to the server. Please try again later.", "bot", "error");
    }
    setLoading(false);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="app">
      <div className="chat-container">
        <div className="chat-header">
          <div className="header-content">
            <div className="vet-icon">🏥</div>
            <div className="header-text">
              <h1>VetBox Triage</h1>
              <p>AI-powered veterinary triage assistant</p>
            </div>
            <button 
              onClick={handleClearChat}
              className="clear-button"
              disabled={loading}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C15.3019 3 18.1885 4.77814 19.7545 7.42909" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M21 3V8C21 8.55228 20.5523 9 20 9H15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              New Chat
            </button>
          </div>
        </div>
        
        <div className="messages-container">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message ${message.sender} ${message.type === "error" ? "error" : ""}`}
            >
              <div className="message-content">
                <div className="message-text">
                  {message.text.split('\n').map((line, index) => (
                    <React.Fragment key={index}>
                      {line}
                      {index < message.text.split('\n').length - 1 && <br />}
                    </React.Fragment>
                  ))}
                </div>
                <div className="message-time">
                  {message.timestamp.toLocaleTimeString([], { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                  })}
                </div>
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="message bot">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        <div className="input-container">
          <form onSubmit={handleSubmit} className="input-form">
            <div className="input-wrapper">
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Describe your pet's symptoms..."
                className="message-input"
                rows={1}
                disabled={loading}
              />
              <button 
                type="submit" 
                disabled={loading || !inputText.trim()}
                className="send-button"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor"/>
                </svg>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default App;
