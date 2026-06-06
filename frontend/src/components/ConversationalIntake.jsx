import { useEffect, useRef, useState } from "react";
import { startIntakeSession, submitIntakeAnswer } from "../api/client.js";

export default function ConversationalIntake({ onComplete }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]); // [{ role: 'assistant'|'user', content }]
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  // Track raw user answers in order (for mock-mode profile assembly)
  const userAnswersRef = useRef([]);

  useEffect(() => {
    let active = true;
    async function start() {
      try {
        const { session_id, question } = await startIntakeSession();
        if (!active) return;
        setSessionId(session_id);
        setMessages([{ role: "assistant", content: question }]);
      } catch (err) {
        setError(err.message);
      }
    }
    start();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || !sessionId || busy) return;
    setError("");
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    const priorAnswers = userAnswersRef.current.slice();
    userAnswersRef.current.push(text);
    setBusy(true);
    try {
      const result = await submitIntakeAnswer(sessionId, text, priorAnswers);
      if (result.complete && result.profile) {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "Got it — searching trials now…" },
        ]);
        onComplete(result.profile);
        return;
      }
      if (result.question) {
        setMessages((m) => [...m, { role: "assistant", content: result.question }]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-intake">
      <div className="chat-intake__head">
        <h2 className="chat-intake__title">Quick chat about your situation</h2>
        <p className="chat-intake__hint">
          I&apos;ll ask just enough to find good matches — usually 4–8 questions.
        </p>
      </div>

      <div className="chat-intake__scroll" ref={scrollRef}>
        {messages.map((m, i) => (
          <div
            key={i}
            className={"chat-msg chat-msg--" + (m.role === "user" ? "user" : "bot")}
          >
            <div className="chat-msg__bubble">{m.content}</div>
          </div>
        ))}
        {busy && (
          <div className="chat-msg chat-msg--bot">
            <div className="chat-msg__bubble chat-msg__bubble--typing">
              <span /> <span /> <span />
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="intake__error" role="alert">
          {error}
        </p>
      )}

      <form className="chat-intake__form" onSubmit={handleSubmit}>
        <input
          type="text"
          className="field__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your answer…"
          disabled={!sessionId || busy}
          autoFocus
        />
        <button
          type="submit"
          className="btn btn--primary"
          disabled={!input.trim() || !sessionId || busy}
        >
          Send
        </button>
      </form>
    </div>
  );
}
