import React, { useState } from "react";

type ChatResponse = {
  follow_up_question: string | null;
  error?: string;
} | { error: string } | null;

function App() {
  const [userAnswer, setUserAnswer] = useState("");
  const [response, setResponse] = useState<ChatResponse>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResponse(null);
    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_answer: userAnswer }),
      });
      const data = await res.json();
      setResponse(data);
    } catch (err) {
      setResponse({ error: "Failed to get response from server." });
    }
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 500, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h2>Triage Chat</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          rows={4}
          style={{ width: "100%" }}
          value={userAnswer}
          onChange={(e) => setUserAnswer(e.target.value)}
          placeholder="Describe your symptoms..."
        />
        <button type="submit" disabled={loading || !userAnswer}>
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
      {response && (
        <div style={{ marginTop: 20 }}>
          {"error" in response ? (
            <div style={{ color: "red" }}>{response.error}</div>
          ) : (
            <>
              <div>
                <strong>Bot:</strong> {response.follow_up_question}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
