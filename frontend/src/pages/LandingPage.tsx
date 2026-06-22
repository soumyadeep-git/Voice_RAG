import { useNavigate } from 'react-router-dom'
import { DemoPlayer } from '../components/DemoPlayer'
import './landing.css'

const FEATURES = [
  {
    n: '01',
    title: 'Grounded & cited',
    body: 'Every answer is traced back to the exact passage it came from. No source, no claim.',
  },
  {
    n: '02',
    title: 'Conflict-aware',
    body: 'When two documents disagree, it surfaces the contradiction instead of guessing.',
  },
  {
    n: '03',
    title: 'Voice-native, with memory',
    body: 'Speak naturally, interrupt mid-answer, and pick up the thread across turns.',
  },
]

const STEPS = [
  { n: '01', title: 'Upload', body: 'Drop in PDFs, markdown, or text. We parse and index them privately.' },
  { n: '02', title: 'Ask out loud', body: 'Talk to your documents and barge in anytime to refine.' },
  { n: '03', title: 'Get cited answers', body: 'Receive grounded answers with sources and conflict flags.' },
]

export function LandingPage() {
  const navigate = useNavigate()
  const launch = () => navigate('/app')

  return (
    <div className="lp">
      <div className="lp-grain" aria-hidden />

      <header className="lp-nav">
        <a className="lp-brand" href="/">
          <span className="lp-brand-mark" />
          ASK_MY_NOTES
        </a>
        <nav className="lp-nav-links">
          <a href="#features">// features</a>
          <a href="#how">// how_it_works</a>
          <a href="https://github.com/soumyadeep-git/Voice_RAG" target="_blank" rel="noreferrer">
            github ↗
          </a>
        </nav>
        <button className="lp-btn lp-btn--solid" onClick={launch}>
          LAUNCH ▸
        </button>
      </header>

      <section className="lp-hero">
        <p className="lp-kicker">// voice_agent — grounded document Q&amp;A</p>
        <h1 className="lp-title">
          Talk to your <em>documents.</em>
        </h1>
        <p className="lp-sub">
          Upload your files and interrogate them by voice. Every answer is grounded in your own
          sources — <i>cited, verified,</i> and flagged when sources disagree.
        </p>
        <div className="lp-cta">
          <button className="lp-btn lp-btn--solid lp-btn--lg" onClick={launch}>
            Launch the app ▸
          </button>
          <a className="lp-btn lp-btn--ghost lp-btn--lg" href="#demo">
            Watch the demo
          </a>
        </div>
      </section>

      <section id="demo" className="lp-demo-wrap">
        <DemoPlayer />
      </section>

      <section id="features" className="lp-features">
        {FEATURES.map((f) => (
          <article key={f.n} className="lp-feature">
            <span className="lp-feature-n">{f.n}</span>
            <h3 className="lp-feature-title">{f.title}</h3>
            <p className="lp-feature-body">{f.body}</p>
          </article>
        ))}
      </section>

      <section id="how" className="lp-how">
        <p className="lp-kicker lp-kicker--center">// how_it_works</p>
        <div className="lp-steps">
          {STEPS.map((s) => (
            <div key={s.n} className="lp-step">
              <span className="lp-step-n">{s.n}</span>
              <h4 className="lp-step-title">{s.title}</h4>
              <p className="lp-step-body">{s.body}</p>
            </div>
          ))}
        </div>
        <button className="lp-btn lp-btn--solid lp-btn--lg lp-how-cta" onClick={launch}>
          Start a session ▸
        </button>
      </section>

      <footer className="lp-footer">
        <span>© 2026 ASK_MY_NOTES</span>
        <span className="lp-footer-meta">voice-enabled · grounded · cited</span>
      </footer>
    </div>
  )
}
