import { useNavigate } from "react-router-dom";

export function ErrorState({ message, onRetry }) {
  const navigate = useNavigate();
  return (
    <div className="state-card state-card--error" role="alert">
      <div className="state-card__icon" aria-hidden="true">!</div>
      <h2 className="state-card__title">Something went wrong</h2>
      <p className="state-card__body">
        {message || "We couldn't complete your search. Please try again."}
      </p>
      <div className="state-card__actions">
        {onRetry && (
          <button className="btn btn--primary" onClick={onRetry}>
            Try again
          </button>
        )}
        <button className="btn btn--ghost" onClick={() => navigate("/")}>
          Start over
        </button>
      </div>
    </div>
  );
}

export function EmptyState() {
  const navigate = useNavigate();
  return (
    <div className="state-card" role="status">
      <div className="state-card__icon" aria-hidden="true">∅</div>
      <h2 className="state-card__title">No matching trials found</h2>
      <p className="state-card__body">
        We couldn&apos;t find recruiting trials for that search. Try broadening
        your condition description, removing very specific terms, or widening
        your location.
      </p>
      <div className="state-card__actions">
        <button className="btn btn--primary" onClick={() => navigate("/")}>
          Adjust your search
        </button>
      </div>
    </div>
  );
}
