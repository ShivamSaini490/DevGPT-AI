import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Logo from "./Logo";

gsap.registerPlugin(useGSAP);

interface Word {
  text: string;
  accent?: boolean;
}

// Intro tagline, revealed word by word. `accent` words get the gradient.
const PHRASES: Word[][] = [
  [{ text: "Think" }, { text: "It." }],
  [{ text: "Say" }, { text: "It." }],
  [{ text: "DevGPT", accent: true }, { text: "Reply" }, { text: "It." }],
];

const TAGLINE = PHRASES.map((p) => p.map((w) => w.text).join(" ")).join(" ");

/**
 * Full-screen intro shown on page load. Plays the tagline, waits until the
 * app is `ready`, then lifts away and calls `onDone`.
 */
interface SplashProps {
  ready: boolean;
  onDone: () => void;
}

export default function Splash({ ready, onDone }: SplashProps) {
  const scope = useRef<HTMLDivElement>(null);
  const [introDone, setIntroDone] = useState(false);
  const exitingRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const reduceMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useGSAP(
    () => {
      const words = gsap.utils.toArray<HTMLElement>(".splash-word");
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

      // The inner spark pops in and turns once the D has landed.
      tl.from(
        ".splash-mark .logo-spark",
        { scale: 0, rotate: -180, transformOrigin: "50% 50%", duration: 0.6, ease: "back.out(2.2)" },
        "-=0.25"
      );

      // One word at a time, with a short breath at the end of each phrase.
      let at = 0.35;
      PHRASES.forEach((phrase, p) => {
        phrase.forEach(() => {
          const word = words.shift();
          if (word) {
            tl.fromTo(
              word,
              { opacity: 0, yPercent: 70, filter: "blur(12px)" },
              { opacity: 1, yPercent: 0, filter: "blur(0px)", duration: 0.6, ease: "power3.out" },
              at
            );
          }
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
    const root = scope.current;
    if (exitingRef.current || !root) return;
    exitingRef.current = true;

    gsap
      .timeline({ onComplete: () => onDoneRef.current?.() })
      .to(root.querySelectorAll(".splash-word, .splash-mark"), {
        opacity: 0,
        yPercent: -60,
        filter: "blur(10px)",
        duration: reduceMotion ? 0.01 : 0.45,
        ease: "power2.in",
        stagger: reduceMotion ? 0 : 0.03,
      })
      .to(root, { opacity: 0, duration: reduceMotion ? 0.01 : 0.35, ease: "power1.out" }, "-=0.15");
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
      <Logo size={52} className="splash-mark" />

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
