import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { useMatch } from "../context/MatchContext.jsx";
import ProfileSwitcher from "./ProfileSwitcher.jsx";
import AlertsBell from "./AlertsBell.jsx";

export default function Header() {
  const { isAuthed, account, logout } = useAuth();
  const { data: matchData } = useMatch();
  const location = useLocation();
  const navigate = useNavigate();

  const hasResults = !!matchData && !location.pathname.startsWith("/results");

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
        {/* Left: brand + content nav */}
        <div className="site-header__left">
          <Link to="/" className="brand" aria-label="TrialFinder home">
            <span className="brand__mark" aria-hidden="true">✛</span>
            <span className="brand__name">TrialFinder</span>
          </Link>

          <nav className="site-nav" aria-label="Primary">
            {hasResults && (
              <Link to="/results" className="site-nav__link site-nav__link--brand">
                ← Your results
              </Link>
            )}
            <Link to="/what-is-a-clinical-trial" className="site-nav__link">
              What is a trial?
            </Link>
            <Link to="/why-participate" className="site-nav__link">
              Why participate
            </Link>
          </nav>
        </div>

        {/* Right: account controls, visually separated from content nav */}
        <div className="site-header__right">
          {isAuthed ? (
            <>
              <ProfileSwitcher />
              <Link to="/watchlist" className="site-nav__link">
                Watchlist
              </Link>
              <AlertsBell />
              <div className="account-menu">
                <span className="account-menu__email" title={account?.email}>
                  {account?.email}
                </span>
                <button className="btn btn--ghost btn--sm" onClick={handleLogout}>
                  Log out
                </button>
              </div>
            </>
          ) : (
            <Link to="/login" className="btn btn--primary btn--sm">
              Log in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
