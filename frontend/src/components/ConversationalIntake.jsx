import { useEffect, useRef, useState } from "react";
import { startIntakeSession, submitIntakeAnswer } from "../api/client.js";

export default function ConversationalIntake({ onComplete }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]); // [{ role: 'assistant'|'user', content }]
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [turns, setTurns] = useState(0);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const MAX_TURNS = 7;

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

  // Keep the newest message in view. This runs after paint (rAF) because the
  // new bubble has not been laid out yet when the effect first fires, so
  // reading scrollHeight immediately gives a stale value and the view sticks
  // one message behind. Also depends on `busy` so the typing indicator
  // scrolls into view too.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const id = requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    });
    return () => cancelAnimationFrame(id);
  }, [messages, busy]);

  async function send(text) {
    if (!text || !sessionId || busy) return;
    setError("");
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    const priorAnswers = userAnswersRef.current.slice();
    userAnswersRef.current.push(text);
    setBusy(true);
    try {
      const result = await submitIntakeAnswer(sessionId, text, priorAnswers);
      setTurns(result.turns_so_far ?? turns + 1);

      if (result.complete && result.profile) {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "Got it, searching trials now." },
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
      // Return focus so the user can keep typing without reaching for a click.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    send(input.trim());
  }

  return (
    <div className="chat-intake">
      <div className="chat-intake__head">
        <h2 className="chat-intake__title">Quick chat about your situation</h2>
        <p className="chat-intake__hint">
          A few short questions, then we search. You can answer &ldquo;skip&rdquo;
          to any question you would rather not answer.
        </p>
        <div
          className="chat-intake__progress"
          role="progressbar"
          aria-valuenow={Math.min(turns, MAX_TURNS)}
          aria-valuemin={0}
          aria-valuemax={MAX_TURNS}
          aria-label="Interview progress"
        >
          <div
            className="chat-intake__progress-fill"
            style={{ width: `${Math.min((turns / MAX_TURNS) * 100, 100)}%` }}
          />
        </div>
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
          ref={inputRef}
          type="text"
          className="field__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your answer..."
          disabled={!sessionId || busy}
          autoFocus
        />
        {/* One-tap escape hatch. Sending "skip" is what the backend reads as
            a decline, and two in a row ends the interview. */}
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => send("skip")}
          disabled={!sessionId || busy}
          title="Skip this question"
        >
          Skip
        </button>
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
