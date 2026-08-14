import { Link } from "react-router-dom";

export default function Privacy() {
  return (
    <article className="article">
      <header className="article__head">
        <p className="article__eyebrow">Legal</p>
        <h1 className="article__title">Privacy Policy</h1>
        <p className="article__lede">
          TrialFinder handles health information, which is among the most
          sensitive data a person can share. This page explains exactly what we
          collect, why we collect it, and what we do to protect it.
        </p>
        <p className="article__meta">Last updated: August 2026</p>
      </header>

      <section className="article__section">
        <h2>What we collect</h2>
        <p>
          When you search for trials, you provide details about your condition,
          treatment history, location, medications, and optionally biomarker
          results and age. If you create an account, we also store your email
          address and a cryptographic hash of your password.
        </p>
        <p>
          We do not collect your name, date of birth, Social Security number,
          insurance member ID, or medical record number. We ask for the minimum
          needed to match you to relevant trials.
        </p>
      </section>

      <section className="article__section">
        <h2>How your data is protected</h2>
        <ul className="reasons">
          <li>
            <strong>Passwords are never stored.</strong> We store only a bcrypt
            hash. Nobody, including us, can read your password.
          </li>
          <li>
            <strong>Encrypted in transit.</strong> All traffic uses HTTPS, and
            the production service refuses unencrypted connections.
          </li>
          <li>
            <strong>Your data is yours alone.</strong> Every request is checked
            against the logged-in account. One user cannot read, change, or
            delete another user&apos;s profiles or saved trials.
          </li>
          <li>
            <strong>Sessions expire.</strong> Login sessions are short-lived,
            and changing your password immediately ends every existing session.
          </li>
          <li>
            <strong>Database is not publicly reachable.</strong> It accepts
            connections only from the application server, never from the open
            internet.
          </li>
          <li>
            <strong>Abuse protection.</strong> Login attempts, account creation,
            and AI searches are rate limited, and repeated failed logins
            temporarily lock the account.
          </li>
        </ul>
      </section>

      <section className="article__section">
        <h2>Who we share it with</h2>
        <p>
          We do not sell your data. We do not share it with advertisers, data
          brokers, insurers, or employers. We have no advertising on this site.
        </p>
        <p>
          To produce your matches, your condition and treatment details are sent
          to two services: ClinicalTrials.gov, which is operated by the U.S.
          National Library of Medicine, and our AI provider, which generates the
          plain-English explanations. These providers process the text to return
          a result. We do not send them your email address or any account
          identifier, so the clinical text is not linked to your identity on
          their side.
        </p>
        <p>
          We may disclose information if legally compelled to do so, for example
          by a valid court order.
        </p>
      </section>

      <section className="article__section">
        <h2>Your choices</h2>
        <p>
          You can search without creating an account. If you do have an account,
          you can delete any patient profile or saved trial at any time from the
          app, which permanently removes it along with its watchlist entries.
        </p>
        <p>
          To delete your entire account and all associated data, email us and we
          will action it. Depending on where you live, you may have additional
          rights to access, correct, export, or erase your data under laws such
          as the GDPR or the CCPA.
        </p>
      </section>

      <section className="article__section">
        <h2>An important limitation</h2>
        <p>
          TrialFinder is an informational tool, not a healthcare provider. We
          are not a HIPAA covered entity, which means the information you enter
          here does not carry the same legal protections as records held by your
          doctor or hospital. Please keep that in mind and share only what you
          are comfortable sharing.
        </p>
      </section>

      <section className="article__section">
        <h2>Cookies and tracking</h2>
        <p>
          We use no advertising cookies and no third-party analytics trackers.
          Your login session is stored in your own browser and is sent only to
          our API.
        </p>
      </section>

      <div className="article__cta">
        <Link to="/terms" className="btn btn--ghost">
          Terms of Use
        </Link>
        <Link to="/" className="btn btn--primary">
          Find trials
        </Link>
      </div>
    </article>
  );
}
