import { Link } from "react-router-dom";

export default function WhatIsTrial() {
  return (
    <article className="article">
      <header className="article__head">
        <p className="article__eyebrow">Patient education</p>
        <h1 className="article__title">What is a clinical trial?</h1>
        <p className="article__lede">
          A clinical trial is a research study that tests whether a new
          treatment is safe and whether it works better than what doctors use
          today. Every medication and procedure you have ever taken existed
          because real patients volunteered for a trial first.
        </p>
      </header>

      <section className="article__section">
        <h2>Why clinical trials exist</h2>
        <p>
          Every new therapy has to be tested in people before it can become
          standard care. The first goal is safety. The next goal is figuring
          out how well it works compared to the treatments already available.
          This is how medicine moves forward. Without volunteers, we would not
          have new cancer drugs, new vaccines, or improved surgical
          techniques.
        </p>
      </section>

      <section className="article__section">
        <h2>The four phases, in plain English</h2>
        <div className="phases">
          <div className="phase">
            <div className="phase__num">I</div>
            <div>
              <h3 className="phase__title">Phase I: Is it safe?</h3>
              <p>
                A small group of about 20 to 80 volunteers receives the new
                treatment. Researchers use this phase to find a safe dose and
                watch for side effects. In cancer, Phase I usually enrolls
                patients who have run out of standard options.
              </p>
            </div>
          </div>

          <div className="phase">
            <div className="phase__num">II</div>
            <div>
              <h3 className="phase__title">Phase II: Does it work?</h3>
              <p>
                A larger group of about 100 to 300 people helps researchers
                see whether the treatment actually helps and how often side
                effects show up. Many cancer trials that patients hear about
                are in Phase II.
              </p>
            </div>
          </div>

          <div className="phase">
            <div className="phase__num">III</div>
            <div>
              <h3 className="phase__title">Phase III: Is it better?</h3>
              <p>
                Hundreds or thousands of people are randomized to either the
                new treatment or the current standard of care. This lets
                researchers compare them fairly. Strong Phase III results are
                usually what regulators need before approving a drug.
              </p>
            </div>
          </div>

          <div className="phase">
            <div className="phase__num">IV</div>
            <div>
              <h3 className="phase__title">Phase IV: Long-term follow-up</h3>
              <p>
                After a treatment is approved, Phase IV trials track how it
                performs in the wider population over years. Researchers look
                for rare side effects and long-term outcomes.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="article__section">
        <h2>What enrolling actually looks like</h2>
        <p>
          Most trials start with a screening visit. A study coordinator checks
          whether you meet the trial&apos;s eligibility criteria. That
          usually covers your cancer type, prior treatments, organ function,
          and current medications. If you qualify and decide to enroll, you
          sign an informed consent document. It explains what the trial
          involves, the known risks, and your right to leave at any time.
        </p>
        <p>
          Treatment then follows a fixed schedule with regular checkups. You
          can stop participating at any point, for any reason. Doing so does
          not affect the care you receive outside the study.
        </p>
      </section>

      <section className="article__section">
        <h2>Common terms you will see</h2>
        <dl className="glossary">
          <dt>Inclusion criteria</dt>
          <dd>The conditions you must meet to qualify. This might include a specific cancer type or prior therapies.</dd>
          <dt>Exclusion criteria</dt>
          <dd>Conditions that would disqualify you, such as certain medications or organ issues.</dd>
          <dt>Randomization</dt>
          <dd>Being assigned by chance to one of two or more treatment groups so the comparison stays fair.</dd>
          <dt>Placebo</dt>
          <dd>An inactive substance used in some trials for comparison. In serious illness trials, placebo is usually added to standard care rather than replacing it.</dd>
          <dt>Standard of care</dt>
          <dd>The treatment your doctor would normally give you outside the trial.</dd>
          <dt>NCT ID</dt>
          <dd>A unique identifier like NCT04685135 that tracks every registered trial on ClinicalTrials.gov.</dd>
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
        This page is informational and is not medical advice. Please discuss
        any clinical trial with your treating physician.
      </p>
    </article>
  );
}
