import { useEffect, useState } from "react";

const MESSAGES = [
  "Searching 500,000+ clinical trials…",
  "Reading recent trial results…",
  "Analyzing eligibility criteria…",
  "Generating personalized matches…",
];

export default function LoadingState() {
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    // Advance the status message every ~2.8s, stopping on the last one.
    const id = setInterval(() => {
      setIdx((i) => (i < MESSAGES.length - 1 ? i + 1 : i));
    }, 2800);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading__spinner" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <p className="loading__message">{MESSAGES[idx]}</p>
      <ul className="loading__progress" aria-hidden="true">
        {MESSAGES.map((_, i) => (
          <li
            key={i}
            className={"loading__dot" + (i <= idx ? " is-on" : "")}
          />
        ))}
      </ul>
      <p className="loading__note">
        This usually takes 10–20 seconds while we pull live trial data.
      </p>
    </div>
  );
}
