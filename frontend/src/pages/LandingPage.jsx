import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import {
  ArrowRight,
  Brain,
  Calculator,
  CloudSun,
  Code2,
  Database,
  ExternalLink,
  FileText,
  Globe,
  Mic,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Upload,
  Zap,
} from "lucide-react";
import Link from "../components/Link";
import ThemeToggle from "../components/ThemeToggle";
import FeatureStack from "./landing/FeatureStack";
import HeroField from "./landing/HeroField";
import ParticleRing from "./landing/ParticleRing";
import Showcase from "./landing/Showcase";
import UseCases from "./landing/UseCases";

gsap.registerPlugin(useGSAP, ScrollTrigger);

const REPO_URL = "https://github.com/ShivamSaini490/DevGPT-AI";
const SPARK =
  "M16 2c1.2 7.4 6.6 12.8 14 14-7.4 1.2-12.8 6.6-14 14-1.2-7.4-6.6-12.8-14-14C9.4 14.8 14.8 9.4 16 2z";

// Each phrase stays on one line; the title only wraps between phrases.
const TAGLINE = [
  [{ text: "Think" }, { text: "It." }],
  [{ text: "Say" }, { text: "It." }],
  [{ text: "DevGPT", accent: true }, { text: "Reply" }, { text: "It." }],
];

const STATEMENT =
  "DevGPT is an agentic assistant that works with tools, not just text. It searches the web, reads your files, remembers what matters and does the math, then streams the answer back as it writes.";

const MARQUEE_ICONS = [
  Globe,
  FileText,
  Brain,
  CloudSun,
  TrendingUp,
  Calculator,
  Zap,
  Mic,
  Search,
  Database,
  Code2,
  Sparkles,
  Upload,
  ShieldCheck,
];

const NAV = [
  { href: "#features", label: "Features" },
  { href: "#use-cases", label: "Use cases" },
  { href: "#start", label: "Get started" },
];

function scrollToHash(event, hash) {
  event.preventDefault();
  document.querySelector(hash)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function LandingPage({ theme, onToggleTheme, introDone, onNavigate }) {
  const root = useRef(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useGSAP(
    () => {
      if (!introDone) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

      // ---- Hero: tagline word by word, then the supporting copy.
      gsap
        .timeline({ defaults: { ease: "power3.out" } })
        .from(".hero-field", { opacity: 0, duration: 1.4, ease: "power2.out" })
        .from(".l-eyebrow", { y: 12, opacity: 0, duration: 0.6 }, 0)
        .from(".l-word", { yPercent: 70, opacity: 0, filter: "blur(12px)", duration: 0.75, stagger: 0.09 }, "-=0.3")
        .from(".l-sub", { y: 16, opacity: 0, duration: 0.7 }, "-=0.35")
        .from(".l-ctas > *", { y: 14, opacity: 0, duration: 0.6, stagger: 0.08 }, "-=0.45")
        .from(".showcase", { y: 60, opacity: 0, duration: 1.1 }, "-=0.5");

      // ---- Showcase: the stage grows to full size as it scrolls in.
      gsap.fromTo(
        ".showcase",
        { scale: 0.86, borderRadius: 48 },
        {
          scale: 1,
          borderRadius: 28,
          ease: "none",
          scrollTrigger: { trigger: ".showcase-wrap", start: "top 85%", end: "top 15%", scrub: 0.6 },
        }
      );

      // The mock conversation plays once the stage is in view.
      gsap
        .timeline({ scrollTrigger: { trigger: ".showcase", start: "top 55%", once: true } })
        .from(".sc-user", { x: 30, opacity: 0, duration: 0.5, ease: "power2.out" })
        .from(".sc-chip", { y: 8, opacity: 0, duration: 0.35, stagger: 0.35 }, "+=0.3")
        .from(".sc-token", { opacity: 0, duration: 0.05, stagger: 0.045 }, "+=0.2");

      // ---- Statement: words light up as you read down the page.
      gsap.fromTo(
        ".st-word",
        { opacity: 0.14 },
        {
          opacity: 1,
          ease: "none",
          stagger: 0.1,
          scrollTrigger: { trigger: ".statement", start: "top 78%", end: "bottom 45%", scrub: 0.4 },
        }
      );

      // ---- Feature stack: each card settles back as the next one slides over it.
      const mm = gsap.matchMedia();
      mm.add("(min-width: 901px)", () => {
        const cards = gsap.utils.toArray(".fs-sticky");
        cards.forEach((card, i) => {
          const next = cards[i + 1];
          if (!next) return;
          gsap.to(card.firstElementChild, {
            scale: 0.9,
            opacity: 0.35,
            filter: "blur(2px)",
            ease: "none",
            scrollTrigger: { trigger: next, start: "top bottom", end: "top 30%", scrub: 0.5 },
          });
        });
      });

      gsap.utils.toArray(".fs-text").forEach((el) => {
        gsap.from(el.children, {
          y: 24,
          opacity: 0,
          duration: 0.7,
          stagger: 0.08,
          ease: "power3.out",
          scrollTrigger: { trigger: el, start: "top 80%", once: true },
        });
      });

      // ---- Generic reveals.
      gsap.set(".reveal", { opacity: 0 });
      ScrollTrigger.batch(".reveal", {
        start: "top 88%",
        once: true,
        onEnter: (elements) =>
          gsap.fromTo(
            elements,
            { y: 28, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.8, ease: "power3.out", stagger: 0.08, overwrite: true, clearProps: "transform" }
          ),
      });

      // ---- Closing card lifts in; the giant wordmark rises letter by letter.
      gsap.fromTo(
        ".launch",
        { scale: 0.92, borderRadius: 56 },
        {
          scale: 1,
          borderRadius: 32,
          ease: "none",
          scrollTrigger: { trigger: ".launch", start: "top bottom", end: "top 35%", scrub: 0.6 },
        }
      );

      gsap.from(".wm-letter", {
        yPercent: 110,
        ease: "none",
        stagger: 0.06,
        scrollTrigger: { trigger: ".wordmark-big", start: "top bottom", end: "bottom bottom", scrub: 0.6 },
      });

      return () => mm.revert();
    },
    { scope: root, dependencies: [introDone] }
  );

  return (
    <div className="landing" ref={root} data-intro={introDone ? "done" : "playing"}>
      <header className={`l-nav ${scrolled ? "scrolled" : ""}`}>
        <div className="l-nav-inner">
          <a href="#top" className="l-brand" onClick={(e) => scrollToHash(e, "#top")}>
            <svg viewBox="0 0 32 32" width="20" height="20" aria-hidden="true">
              <path fill="var(--accent)" d={SPARK} />
            </svg>
            DevGPT
          </a>

          <nav className="l-links" aria-label="Sections">
            {NAV.map((item) => (
              <a key={item.href} href={item.href} onClick={(e) => scrollToHash(e, item.href)}>
                {item.label}
              </a>
            ))}
          </nav>

          <div className="l-nav-actions">
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
            <Link to="/chat" onNavigate={onNavigate} className="btn btn-primary btn-sm">
              Open chat
              <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      </header>

      <main id="top">
        {/* ---------- Hero ---------- */}
        <div className="hero-stage">
          <HeroField theme={theme} />
        <section className="l-hero">
          <span className="l-eyebrow">
            <span className="l-eyebrow-dot" />
            Agentic AI assistant
          </span>

          <h1 className="l-title" aria-label="Think It. Say It. DevGPT Reply It.">
            {TAGLINE.map((phrase, p) => (
              <span key={p} className="l-phrase" aria-hidden="true">
                {phrase.map((word, w) => (
                  <span key={w} className={`l-word ${word.accent ? "accent" : ""}`}>
                    {word.text}
                  </span>
                ))}
              </span>
            ))}
          </h1>

          <p className="l-sub">
            An AI assistant that searches the web, reads your documents, remembers what matters to you and
            streams its answers live.
          </p>

          <div className="l-ctas">
            <Link to="/chat" onNavigate={onNavigate} className="btn btn-contrast btn-lg">
              Start chatting
              <ArrowRight size={18} />
            </Link>
          </div>
        </section>
        </div>

        <Showcase />

        {/* ---------- Icon marquee ---------- */}
        <div className="icon-marquee" aria-hidden="true">
          <div className="icon-track">
            {[...MARQUEE_ICONS, ...MARQUEE_ICONS].map((Icon, i) => (
              <span key={i} className={`icon-dot ${i % 7 === 3 ? "lit" : ""}`}>
                <Icon size={18} strokeWidth={1.6} />
              </span>
            ))}
          </div>
        </div>

        {/* ---------- Statement ---------- */}
        <section className="l-section statement-wrap">
          <p className="statement" aria-label={STATEMENT}>
            {STATEMENT.split(" ").map((word, i) => (
              <span key={i} className={`st-word ${word === "DevGPT" ? "accent-text" : ""}`} aria-hidden="true">
                {word}{" "}
              </span>
            ))}
          </p>
        </section>

        {/* ---------- Stacking features ---------- */}
        <FeatureStack onNavigate={onNavigate} />

        {/* ---------- Use cases ---------- */}
        <UseCases />

        {/* ---------- Two CTAs ---------- */}
        <section className="l-section duo" id="start">
          <div className="duo-col reveal">
            <span className="duo-kicker">Nothing to install</span>
            <h3>
              For quick questions
              <br />
              <span className="muted">Just start typing</span>
            </h3>
            <Link to="/chat" onNavigate={onNavigate} className="btn btn-contrast btn-sm">
              Start chatting
            </Link>
          </div>
          <div className="duo-col reveal">
            <span className="duo-kicker">PDF · DOCX · TXT · MD · PY · CSV</span>
            <h3>
              For your documents
              <br />
              <span className="muted">Upload and ask away</span>
            </h3>
            <Link to="/chat" onNavigate={onNavigate} className="btn btn-ghost btn-sm">
              Upload in chat
            </Link>
          </div>
        </section>

        {/* ---------- Closing card ---------- */}
        <section className="launch-wrap">
          <div className="launch force-dark">
            <ParticleRing />
            <div className="launch-copy">
              <h2>
                Think it. Say it.
                <br />
                <span className="accent-text">DevGPT</span> replies.
              </h2>
              <p>No account needed. Chats are cleared shortly after you close the tab, and always within 24 hours.</p>
              <div className="launch-ctas">
                <Link to="/chat" onNavigate={onNavigate} className="btn btn-light btn-sm">
                  Open DevGPT chat
                </Link>
                <a href={REPO_URL} target="_blank" rel="noreferrer noopener" className="btn btn-outline-light btn-sm">
                  View source <ExternalLink size={13} />
                </a>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ---------- Footer ---------- */}
      <footer className="l-footer">
        <div className="foot-top">
          <p className="foot-line">Think it. Say it.</p>
          <div className="foot-cols">
            <div>
              <h4>Product</h4>
              <Link to="/chat" onNavigate={onNavigate}>
                Chat
              </Link>
              <a href="#features" onClick={(e) => scrollToHash(e, "#features")}>
                Features
              </a>
              <a href="#use-cases" onClick={(e) => scrollToHash(e, "#use-cases")}>
                Use cases
              </a>
            </div>
            <div>
              <h4>Resources</h4>
              <a href="/docs" target="_blank" rel="noreferrer">
                API docs
              </a>
              <a href={REPO_URL} target="_blank" rel="noreferrer noopener">
                GitHub
              </a>
              <a href={`${REPO_URL}/blob/main/LICENSE`} target="_blank" rel="noreferrer noopener">
                Apache 2.0 license
              </a>
            </div>
          </div>
        </div>

        <div className="wordmark-big" aria-label="DevGPT">
          {"DevGPT".split("").map((letter, i) => (
            <span key={i} className="wm-clip" aria-hidden="true">
              <span className="wm-letter">{letter}</span>
            </span>
          ))}
        </div>

        <div className="foot-bottom">
          <span>DevGPT</span>
          <span>FastAPI · pgvector · React</span>
        </div>
      </footer>
    </div>
  );
}
