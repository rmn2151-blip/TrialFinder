import { Link } from "react-router-dom";

export default function Header() {
  return (
    <header className="site-header">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <div className="site-header__inner">
        <Link to="/" className="brand" aria-label="TrialFinder home">
          <span className="brand__mark" aria-hidden="true">✛</span>
          <span className="brand__name">TrialFinder</span>
        </Link>
        <span className="brand__tag">Clinical trials that fit you</span>
      </div>
    </header>
  );
}
