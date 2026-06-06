import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import ProfileSwitcher from "./ProfileSwitcher.jsx";

export default function Header() {
  const { isAuthed, account, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/");
  }

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

        <nav className="site-nav" aria-label="Primary">
          <Link to="/what-is-a-clinical-trial" className="site-nav__link">
            What is a trial?
          </Link>
          <Link to="/why-participate" className="site-nav__link">
            Why participate
          </Link>
          {isAuthed ? (
            <>
              <ProfileSwitcher />
              <Link to="/watchlist" className="site-nav__link">
                Watchlist
              </Link>
              <span className="site-nav__email" title={account?.email}>
                {account?.email}
              </span>
              <button className="btn btn--ghost btn--sm" onClick={handleLogout}>
                Log out
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn--primary btn--sm">
              Log in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
