import { Link } from "react-router-dom";

export default function WhyParticipate() {
  return (
    <article className="article">
      <header className="article__head">
        <p className="article__eyebrow">Patient education</p>
        <h1 className="article__title">Why participate in a clinical trial?</h1>
        <p className="article__lede">
          Joining a clinical trial is a personal decision, and only you and your
          doctor can decide whether one is right for you. But for many patients
          — especially those with serious or rare conditions — a trial can mean
          access to therapies years before they reach the general public.
        </p>
      </header>

      <section className="article__section">
        <h2>Potential benefits</h2>
        <ul className="reasons">
          <li>
            <strong>Earlier access to promising therapies.</strong> New
            treatments are often available through trials long before they
            receive approval and reach hospitals broadly.
          </li>
          <li>
            <strong>Close, attentive follow-up.</strong> Trial protocols
            typically include more frequent imaging, lab work, and physician
            visits than routine care. Many patients describe the level of
            monitoring as the most reassuring part of participating.
          </li>
          <li>
            <strong>Care from specialists.</strong> Trials are usually run at
            academic medical centers and research hospitals with deep expertise
            in your specific condition.
          </li>
          <li>
            <strong>Costs that are often covered.</strong> The trial sponsor
            typically pays for the experimental treatment and study-specific
            procedures, though routine care may still go through your
            insurance. Always ask the study team for a written breakdown of
            what&apos;s covered.
          </li>
          <li>
            <strong>Contributing to medicine.</strong> Every approved cancer
            drug, every vaccine, every surgical refinement exists because
            patients before you enrolled. Whether or not the treatment helps
            you personally, your participation helps future patients.
          </li>
        </ul>
      </section>

      <section className="article__section">
        <h2>What to think carefully about</h2>
        <p>
          Trials are research, and research has uncertainty. The investigational
          treatment might work better than standard care, the same, or worse,
          and there can be side effects that aren&apos;t fully understood yet.
          Most trials also involve a stricter schedule than routine care — more
          appointments, more lab draws, sometimes travel to a specific center.
        </p>
        <p>
          A good study team will be upfront about all of this during the
          informed-consent conversation. If something is unclear, ask. You can
          take consent documents home, share them with family, and bring back
          questions. You can also leave a trial at any time, for any reason.
        </p>
      </section>

      <section className="article__section">
        <h2>Questions worth asking the study team</h2>
        <ul className="questions">
          <li>What is this trial actually testing, and what&apos;s the comparison?</li>
          <li>What phase is it, and what are the goals (safety, efficacy, dose-finding)?</li>
          <li>What are the most common and most serious known side effects so far?</li>
          <li>Will I receive the experimental treatment, the standard of care, or both?</li>
          <li>How often will I need to come in, and how long does the trial last?</li>
          <li>Which costs are covered by the sponsor, and which will go through my insurance?</li>
          <li>Can I stay on this trial if I move, or transfer to a closer site?</li>
          <li>What happens if I want to stop participating?</li>
          <li>Who do I call after hours if I have a problem?</li>
        </ul>
      </section>

      <section className="article__section">
        <h2>How to tell a serious site from a sketchy one</h2>
        <p>
          Most U.S. cancer trials are run at major academic centers and have
          robust oversight from an Institutional Review Board (IRB). A few
          signals of a reputable site:
        </p>
        <ul className="reasons">
          <li>The institution publishes peer-reviewed research in your disease area.</li>
          <li>The trial is registered on ClinicalTrials.gov with a valid NCT ID.</li>
          <li>The principal investigator is a board-certified specialist in the relevant field.</li>
          <li>The consent form names a specific IRB and gives you a copy.</li>
        </ul>
        <p>
          TrialFinder surfaces site reputation directly on every result — click
          &ldquo;Show site reputation&rdquo; on any trial card to see publications and
          recent press for the sponsoring center.
        </p>
      </section>

      <div className="article__cta">
        <Link to="/what-is-a-clinical-trial" className="btn btn--ghost">
          ← What is a clinical trial?
        </Link>
        <Link to="/" className="btn btn--primary">
          Find trials for me
        </Link>
      </div>

      <p className="article__disclaimer">
        This page is informational and is not medical advice. The decision to
        join a trial is yours, and should be made together with your treating
        physician.
      </p>
    </article>
  );
}
