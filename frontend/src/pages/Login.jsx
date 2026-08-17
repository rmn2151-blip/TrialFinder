import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { forgotPassword, resetPassword } from "../api/client.js";

// Stages: login, register, verify (email code), forgot (request reset),
// reset (enter code + new password).
export default function Login() {
  const { login, register, verifyEmail, resendVerification } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || "/";

  const [stage, setStage] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [shownCode, setShownCode] = useState("");
  const [busy, setBusy] = useState(false);

  function go(next) {
    setStage(next);
    setError("");
    setNotice("");
    setCode("");
    setShownCode("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setNotice("");

    if (stage === "register" || stage === "reset") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirm) {
        setError("The two passwords do not match. Please retype them.");
        return;
      }
    }

    setBusy(true);
    try {
      if (stage === "register") {
        const result = await register(email, password);
        go("verify");
        if (result?.dev_verification_code) {
          // Either no provider is configured, delivery was rejected, or the
          // operator enabled SHOW_VERIFICATION_CODE. Surface it prominently
          // so nobody is stranded waiting on an inbox.
          setShownCode(result.dev_verification_code);
          setNotice("Account created. Use the code below to continue.");
        } else {
          setNotice("Account created. Check your email for a 6-digit code.");
        }
      } else if (stage === "login") {
        await login(email, password);
        navigate(redirectTo, { replace: true });
      } else if (stage === "verifyFromLogin") {
        await verifyEmail(email, code.trim());
        // Verified now, so complete the original login.
        await login(email, password);
        navigate(redirectTo, { replace: true });
      } else if (stage === "verify") {
        await verifyEmail(email, code.trim());
        navigate(redirectTo, { replace: true });
      } else if (stage === "forgot") {
        const r = await forgotPassword(email);
        go("reset");
        setNotice(
          r?.dev_code
            ? `No email service is configured, so here is your reset code: ${r.dev_code}`
            : r?.message || "If an account exists, a reset code is on its way."
        );
      } else if (stage === "reset") {
        await resetPassword(email, code.trim(), password);
        go("login");
        setPassword("");
        setConfirm("");
        setNotice("Your password has been reset. Log in with your new password.");
      }
    } catch (err) {
      const msg = err.message || "Something went wrong.";
      if (stage === "register" && /already have an account|already exists/i.test(msg)) {
        go("login");
        setPassword("");
        setConfirm("");
        setNotice("You already have an account with this email. Please log in.");
      } else if (/no account found/i.test(msg)) {
        // Offer the obvious next step instead of a dead end.
        setStage("register");
        setPassword("");
        setConfirm("");
        setError("");
        setNotice(
          "No account exists for that email. You can create one now, or go back and try a different address."
        );
      } else if (stage === "login" && /verify your email/i.test(msg)) {
        // Account exists but is unverified. Keep the password so we can
        // finish the login automatically once the code is accepted.
        setStage("verifyFromLogin");
        setCode("");
        setError("");
        setNotice(msg);
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleResend() {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const r = await resendVerification(email);
      setNotice(r.message || "A new code has been sent.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const copy = {
    login: {
      title: "Welcome back",
      sub: "Log in to manage your profiles and watchlist.",
      button: "Log in",
    },
    register: {
      title: "Create your account",
      sub: "Save trials and get alerts when they change.",
      button: "Create account",
    },
    verify: {
      title: "Verify your email",
      sub: "Enter the 6-digit code we sent you.",
      button: "Verify email",
    },
    verifyFromLogin: {
      title: "Verify your email to continue",
      sub: "Your account is not verified yet. Enter the code we just sent.",
      button: "Verify and log in",
    },
    forgot: {
      title: "Forgot your password?",
      sub: "Enter your email and we will send you a reset code.",
      button: "Send reset code",
    },
    reset: {
      title: "Set a new password",
      sub: "Enter the code we sent along with your new password.",
      button: "Reset password",
    },
  }[stage];

  const showPassword = ["login", "register", "reset"].includes(stage);
  const showConfirm = ["register", "reset"].includes(stage);
  const showCode = ["verify", "verifyFromLogin", "reset"].includes(stage);
  const emailLocked = ["verify", "verifyFromLogin", "reset"].includes(stage);

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card__title">{copy.title}</h1>
        <p className="auth-card__subtitle">{copy.sub}</p>

        {notice && <p className="auth-card__notice">{notice}</p>}

        {shownCode && (
          <div className="code-callout">
            <p className="code-callout__label">Your verification code</p>
            <p className="code-callout__value">{shownCode}</p>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => {
                setCode(shownCode);
                // Fill the field for them rather than making them retype it.
              }}
            >
              Use this code
            </button>
          </div>
        )}

        {showCode && (
          <p className="auth-card__spam" role="note">
            <strong>Don&apos;t see the email?</strong> Check your spam or junk
            folder, and search for &ldquo;TrialFinder&rdquo;. Delivery can take
            a minute or two. University and work addresses filter more
            aggressively, so it may land there.
          </p>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span className="field__label">Email</span>
            <input
              type="email"
              className="field__input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              autoFocus={!emailLocked}
              disabled={emailLocked}
              required
            />
          </label>

          {showCode && (
            <label className="field">
              <span className="field__label">6-digit code</span>
              <input
                type="text"
                inputMode="numeric"
                className="field__input"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="123456"
                autoComplete="one-time-code"
                autoFocus
                required
              />
            </label>
          )}

          {showPassword && (
            <label className="field">
              <span className="field__label">
                {stage === "reset" ? "New password" : "Password"}
              </span>
              <input
                type="password"
                className="field__input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={
                  stage === "login" ? "Your password" : "At least 8 characters"
                }
                autoComplete={stage === "login" ? "current-password" : "new-password"}
                required
              />
            </label>
          )}

          {showConfirm && (
            <label className="field">
              <span className="field__label">Confirm password</span>
              <input
                type="password"
                className="field__input"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Retype your password"
                autoComplete="new-password"
                required
              />
            </label>
          )}

          {error && (
            <p className="intake__error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
            {busy ? "Please wait..." : copy.button}
          </button>
        </form>

        <p className="auth-card__security">
          🔒 Your password is encrypted and stored only as an irreversible
          hash. We never sell or share your health information.{" "}
          <Link to="/privacy">Privacy Policy</Link>
        </p>

        <div className="auth-card__links">
          {stage === "login" && (
            <>
              <p>
                New to TrialFinder?{" "}
                <button type="button" className="btn--link" onClick={() => go("register")}>
                  Create an account
                </button>
              </p>
              <p>
                <button type="button" className="btn--link" onClick={() => go("forgot")}>
                  Forgot your password?
                </button>
              </p>
            </>
          )}

          {stage === "register" && (
            <p>
              Already have an account?{" "}
              <button type="button" className="btn--link" onClick={() => go("login")}>
                Log in
              </button>
            </p>
          )}

          {(stage === "verify" || stage === "verifyFromLogin") && (
            <>
              <p>
                Didn&apos;t get the code?{" "}
                <button type="button" className="btn--link" onClick={handleResend} disabled={busy}>
                  Send a new one
                </button>
              </p>
              <p>
                <button type="button" className="btn--link" onClick={() => go("login")}>
                  Back to log in
                </button>
              </p>
            </>
          )}

          {(stage === "forgot" || stage === "reset") && (
            <p>
              <button type="button" className="btn--link" onClick={() => go("login")}>
                Back to log in
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
