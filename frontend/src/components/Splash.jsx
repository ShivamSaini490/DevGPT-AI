import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

// Intro tagline, revealed word by word. `accent` words get the gradient.
const PHRASES = [
  [{ text: "Think" }, { text: "It." }],
  [{ text: "Say" }, { text: "It." }],
  [{ text: "DevGPT", accent: true }, { text: "Reply" }, { text: "It." }],
];

const TAGLINE = PHRASES.map((p) => p.map((w) => w.text).join(" ")).join(" ");

/**
 * Full-screen intro shown on page load. Plays the tagline, waits until the
 * app is `ready`, then lifts away and calls `onDone`.
 */
export default function Splash({ ready, onDone }) {
  const scope = useRef(null);
  const [introDone, setIntroDone] = useState(false);
  const exitingRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const reduceMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useGSAP(
    () => {
      const words = gsap.utils.toArray(".splash-word");
      const tl = gsap.timeline({ onComplete: () => setIntroDone(true) });

      if (reduceMotion) {
        tl.set(words, { opacity: 1 }).to({}, { duration: 0.6 });
        return;
      }

      tl.from(".splash-mark", {
        scale: 0,
        rotate: -120,
        opacity: 0,
        duration: 0.7,
        ease: "back.out(1.8)",
      });

      // One word at a time, with a short breath at the end of each phrase.
      let at = 0.35;
      PHRASES.forEach((phrase, p) => {
        phrase.forEach(() => {
          const word = words.shift();
          tl.fromTo(
            word,
            { opacity: 0, yPercent: 70, filter: "blur(12px)" },
            { opacity: 1, yPercent: 0, filter: "blur(0px)", duration: 0.6, ease: "power3.out" },
            at
          );
          at += 0.16;
        });
        if (p < PHRASES.length - 1) at += 0.18;
      });

      // Hold the full line briefly before leaving.
      tl.to({}, { duration: 0.55 }, at + 0.3);
    },
    { scope }
  );

  const exit = () => {
    if (exitingRef.current) return;
    exitingRef.current = true;

    gsap
      .timeline({ onComplete: () => onDoneRef.current?.() })
      .to(scope.current.querySelectorAll(".splash-word, .splash-mark"), {
        opacity: 0,
        yPercent: -60,
        filter: "blur(10px)",
        duration: reduceMotion ? 0.01 : 0.45,
        ease: "power2.in",
        stagger: reduceMotion ? 0 : 0.03,
      })
      .to(scope.current, { opacity: 0, duration: reduceMotion ? 0.01 : 0.35, ease: "power1.out" }, "-=0.15");
  };

  useEffect(() => {
    if (introDone && ready) exit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [introDone, ready]);

  // Let impatient users skip once the app has data.
  useEffect(() => {
    const skip = () => {
      if (ready) exit();
    };
    window.addEventListener("keydown", skip);
    return () => window.removeEventListener("keydown", skip);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  return (
    <div
      className="splash"
      ref={scope}
      role="status"
      aria-label={TAGLINE}
      onClick={() => ready && exit()}
    >
      <svg className="splash-mark" viewBox="0 0 32 32" width="34" height="34" aria-hidden="true">
        <defs>
          <linearGradient id="splash-g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--spark-a)" />
            <stop offset="1" stopColor="var(--spark-b)" />
          </linearGradient>
        </defs>
        <path
          fill="url(#splash-g)"
          d="M16 2c1.2 7.4 6.6 12.8 14 14-7.4 1.2-12.8 6.6-14 14-1.2-7.4-6.6-12.8-14-14C9.4 14.8 14.8 9.4 16 2z"
        />
      </svg>

      <p className="splash-line" aria-hidden="true">
        {PHRASES.map((phrase, p) => (
          <span className="splash-phrase" key={p}>
            {phrase.map((word, w) => (
              <span key={w} className={`splash-word ${word.accent ? "accent" : ""}`}>
                {word.text}
              </span>
            ))}
          </span>
        ))}
      </p>
    </div>
  );
}
