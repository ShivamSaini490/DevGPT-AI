import { useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { ArrowLeft, ArrowRight, Calculator, Code2, GraduationCap, Search, Sun } from "lucide-react";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// Images live in public/use-cases/. Swap any file for a photo (keep the name,
// or change `image` here) — cards crop to fill.
const asset = (name: string): string => `${import.meta.env.BASE_URL}use-cases/${name}`;

// Pixels of vertical scroll per pixel of horizontal card travel.
const SCROLL_FACTOR = 1.6;

const CASES = [
  {
    icon: Code2,
    who: "Developers",
    title: "Debug faster",
    body: "Paste a stack trace or a snippet, ask for a fix, and get Markdown answers with code blocks.",
    image: asset("developers.svg"),
  },
  {
    icon: GraduationCap,
    who: "Students",
    title: "Study from your notes",
    body: "Upload lecture notes as a PDF and ask DevGPT to explain a section or quiz you on it.",
    image: asset("students.svg"),
  },
  {
    icon: Search,
    who: "Researchers",
    title: "Catch up on what's new",
    body: "Pull the latest from the web and get it summarized, with a note when answers came from search.",
    image: asset("researchers.svg"),
  },
  {
    icon: Calculator,
    who: "Analysts",
    title: "Check the numbers",
    body: "Look up a ticker's latest available quote, then run the math with the calculator tool.",
    image: asset("analysts.svg"),
  },
  {
    icon: Sun,
    who: "Everyday",
    title: "Small questions, quickly",
    body: "Weather before you head out, quick conversions, and answers that keep your preferences in mind.",
    image: asset("everyday.svg"),
  },
];

export default function UseCases() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const railRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLSpanElement>(null);
  const pinRef = useRef<ScrollTrigger | null>(null); // ScrollTrigger while the pinned layout is active

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      // Desktop: pin the section and turn vertical scrolling into sideways travel.
      mm.add("(min-width: 901px) and (prefers-reduced-motion: no-preference)", () => {
        const section = sectionRef.current;
        const viewport = viewportRef.current;
        const rail = railRef.current;
        if (!section || !viewport || !rail) return;
        section.classList.add("is-pinned");

        const distance = () => Math.max(0, rail.scrollWidth - viewport.clientWidth);

        const travel = gsap.to(rail, {
          x: () => -distance(),
          ease: "none",
          scrollTrigger: {
            trigger: section,
            start: "center 52%",
            // Scroll a bit more than the cards travel so the glide feels unhurried.
            end: () => `+=${distance() * SCROLL_FACTOR}`,
            pin: true,
            scrub: 0.8,
            anticipatePin: 1,
            invalidateOnRefresh: true,
            refreshPriority: 1,
            onUpdate: (self) => {
              if (progressRef.current) progressRef.current.style.transform = `scaleX(${self.progress})`;
            },
          },
        });
        pinRef.current = travel.scrollTrigger ?? null;

        // Parallax: each picture drifts inside its frame as the card crosses the screen.
        gsap.utils.toArray<HTMLElement>(".uc-img", rail).forEach((img) => {
          gsap.fromTo(
            img,
            { xPercent: -7 },
            {
              xPercent: 7,
              ease: "none",
              scrollTrigger: {
                trigger: img.parentElement,
                containerAnimation: travel,
                start: "left right",
                end: "right left",
                scrub: true,
              },
            }
          );
        });

        // Cards lift in as they enter from the right.
        gsap.utils.toArray<HTMLElement>(".uc-card", rail).forEach((card) => {
          gsap.from(card, {
            opacity: 0.35,
            scale: 0.94,
            ease: "none",
            scrollTrigger: {
              trigger: card,
              containerAnimation: travel,
              start: "left right",
              end: "left 70%",
              scrub: true,
            },
          });
        });

        return () => {
          section.classList.remove("is-pinned");
          pinRef.current = null;
          gsap.set(rail, { clearProps: "transform" });
        };
      });

      return () => mm.revert();
    },
    { scope: sectionRef }
  );

  const go = (dir: number) => {
    const rail = railRef.current;
    const card = rail?.querySelector<HTMLElement>(".uc-card");
    if (!rail || !card) return;
    const cardStep = card.offsetWidth + parseFloat(getComputedStyle(rail).columnGap || "16");
    const st = pinRef.current;

    if (st) {
      // Pinned: move the page scroll by one card's worth of horizontal travel.
      const step = cardStep * SCROLL_FACTOR;
      const span = st.end - st.start;
      const target = Math.min(st.end, Math.max(st.start, window.scrollY + dir * step));
      // Snap to the nearest card boundary so buttons always land cleanly.
      const offset = target - st.start;
      const snapped = st.start + Math.round(offset / step) * step;
      window.scrollTo({ top: Math.min(st.start + span, Math.max(st.start, snapped)), behavior: "smooth" });
    } else {
      viewportRef.current?.scrollBy({ left: dir * cardStep, behavior: "smooth" });
    }
  };

  return (
    <section className="l-section uc" id="use-cases">
      {/* The inner wrapper is what gets pinned, so the section's padding stays outside it. */}
      <div className="uc-pin" ref={sectionRef}>
      <div className="uc-head reveal">
        <h2>
          Built for every kind
          <br />
          of question
        </h2>
        <p>
          Whether you're shipping code, studying for an exam or just checking the weather, DevGPT picks the
          right tool for the question.
        </p>
      </div>

      <div className="uc-viewport" ref={viewportRef}>
        <div className="uc-rail" ref={railRef}>
          {CASES.map(({ icon: Icon, who, title, body, image }) => (
            <article key={who} className="uc-card">
              <div className="uc-art">
                <img className="uc-img" src={image} alt="" loading="lazy" decoding="async" draggable="false" />
              </div>
              <span className="uc-who">
                <Icon size={14} />
                {who}
              </span>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="uc-foot">
        <div className="uc-nav">
          <button type="button" className="uc-btn" onClick={() => go(-1)} aria-label="Previous">
            <ArrowLeft size={16} />
          </button>
          <button type="button" className="uc-btn" onClick={() => go(1)} aria-label="Next">
            <ArrowRight size={16} />
          </button>
        </div>
        <div className="uc-progress" aria-hidden="true">
          <span ref={progressRef} />
        </div>
      </div>
      </div>
    </section>
  );
}
