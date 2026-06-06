import { Link } from "react-router-dom";

export default function WhatIsTrial() {
  return (
    <article className="article">
      <header className="article__head">
        <p className="article__eyebrow">Patient education</p>
        <h1 className="article__title">What is a clinical trial?</h1>
        <p className="article__lede">
          A clinical trial is a carefully designed research study that tests
          whether a new treatment, device, or approach is safe and works better
          than what doctors already use today. Every medication and procedure
          you&apos;ve ever taken existed only because real patients enrolled in
          trials.
        </p>
      </header>

      <section className="article__section">
        <h2>Why clinical trials exist</h2>
        <p>
          Before a new therapy can become standard care, it has to be tested in
          people — first to confirm it&apos;s safe, then to measure how well it
          works compared to existing options. This is the only way medicine
          actually moves forward. Without volunteers, there would be no new
          cancer drugs, no new vaccines, and no new surgical techniques.
        </p>
      </section>

      <section className="article__section">
        <h2>The four phases, in plain English</h2>
        <div className="phases">
          <div className="phase">
            <div className="phase__num">I</div>
            <div>
              <h3 className="phase__title">Phase I — Is it safe?</h3>
              <p>
                A small group of volunteers (often 20–80 people) receives the
                new treatment so researchers can find a safe dose and watch for
                side effects. Phase I trials sometimes involve healthy
                volunteers, but in cancer they typically enroll patients who have
                run out of standard options.
              </p>
            </div>
          </div>

          <div className="phase">
            <div className="phase__num">II</div>
            <div>
              <h3 className="phase__title">Phase II — Does it work?</h3>
              <p>
                A larger group (around 100–300 people) helps researchers see
                whether the treatment actually helps the condition and how often
                side effects occur. Many cancer trials patients hear about are
                Phase II.
              </p>
            </div>
          </div>

          <div className="phase">
            <div className="phase__num">III</div>
            <div>
              <h3 className="phase__title">Phase III — Is it better?</h3>
              <p>
                Hundreds to thousands of people are randomized to the new
                treatment or the current standard of care so researchers can
                compare them head-to-head. Strong Phase III results are usually
                what regulators need to approve a drug.
              </p>
            </div>
          </div>

          <div className="phase">
            <div className="phase__num">IV</div>
            <div>
              <h3 className="phase__title">Phase IV — Long-term, real-world</h3>
              <p>
                After approval, Phase IV trials track how the treatment performs
                in the broader population over years, looking for rare side
                effects and long-term outcomes.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="article__section">
        <h2>What enrolling actually looks like</h2>
        <p>
          You usually start with a <strong>screening visit</strong> where a study
          coordinator checks whether you meet the trial&apos;s eligibility
          criteria — things like cancer type, prior treatments, organ function,
          and current medications. If you qualify and decide to enroll, you
          sign an <strong>informed consent</strong> document that explains
          exactly what the trial involves, the known risks, and your right to
          leave at any time.
        </p>
        <p>
          From there, treatment is delivered on a fixed schedule with regular
          checkups. You can stop participating at any point, for any reason,
          without affecting the care you receive outside the study.
        </p>
      </section>

      <section className="article__section">
        <h2>Common terms you&apos;ll see</h2>
        <dl className="glossary">
          <dt>Inclusion criteria</dt>
          <dd>The conditions you must meet to qualify (e.g., specific cancer type, prior therapies).</dd>
          <dt>Exclusion criteria</dt>
          <dd>Conditions that would disqualify you (e.g., certain medications, organ issues).</dd>
          <dt>Randomization</dt>
          <dd>Being assigned by chance to one of two or more treatment groups, so the comparison is fair.</dd>
          <dt>Placebo</dt>
          <dd>An inactive substance used in some trials to compare against the active treatment. In serious illness trials, placebo is usually <em>added to</em> standard care, not used in place of it.</dd>
          <dt>Standard of care</dt>
          <dd>The treatment doctors would normally give you outside the trial.</dd>
          <dt>NCT ID</dt>
          <dd>An identifier (e.g., NCT04685135) that uniquely tracks every registered trial on ClinicalTrials.gov.</dd>
        </dl>
      </section>

      <div className="article__cta">
        <Link to="/why-participate" className="btn btn--ghost">
          Why participate →
        </Link>
        <Link to="/" className="btn btn--primary">
          Find trials for me
        </Link>
      </div>

      <p className="article__disclaimer">
        This page is informational and is not medical advice. Always discuss any
        clinical trial with your treating physician.
      </p>
    </article>
  );
}
