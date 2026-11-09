import { forwardRef, useRef } from "react";
import { motion } from "motion/react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Brain, Calculator, FileText, Globe } from "lucide-react";

gsap.registerPlugin(useGSAP);

function greetingFor(date = new Date()): string {
  const hour = date.getHours();
  if (hour < 5) return "Burning the midnight oil?";
  if (hour < 12) return "Good morning. What's on your mind?";
  if (hour < 18) return "What's on your mind?";
  return "Good evening. What's on your mind?";
}

export const Hero = forwardRef<HTMLDivElement>(function Hero(_props, ref) {
  const scope = useRef<HTMLHeadingElement>(null);
  const greeting = useRef(greetingFor()).current;

  useGSAP(
    () => {
      gsap.from(".hero-word", {
        yPercent: 60,
        opacity: 0,
        filter: "blur(10px)",
        duration: 0.9,
        ease: "power3.out",
        stagger: 0.07,
        delay: 0.15,
      });
    },
    { scope }
  );

  return (
    <motion.div
      ref={ref}
      className="hero"
      exit={{ opacity: 0, y: -16, filter: "blur(8px)", transition: { duration: 0.3 } }}
    >
      <h1 ref={scope} aria-label={greeting}>
        {greeting.split(" ").map((word, i) => (
          <span className="hero-word" aria-hidden="true" key={`${word}-${i}`}>
            {word}
          </span>
        ))}
      </h1>
    </motion.div>
  );
});

const SUGGESTIONS = [
  { icon: Globe, label: "Search the web for the latest AI agent news" },
  { icon: FileText, label: "Summarize the document I uploaded" },
  { icon: Brain, label: "Remember that I prefer concise answers" },
  { icon: Calculator, label: "Calculate 125 × 48 / 6" },
];

interface SuggestionsProps {
  onPick: (text: string) => void;
}

export const Suggestions = forwardRef<HTMLDivElement, SuggestionsProps>(function Suggestions({ onPick }, ref) {
  const scope = useRef<HTMLUListElement>(null);

  useGSAP(
    () => {
      gsap.from(".suggestion", {
        y: 10,
        opacity: 0,
        duration: 0.6,
        ease: "power2.out",
        stagger: 0.06,
        delay: 0.55,
      });
    },
    { scope }
  );

  return (
    <motion.div
      ref={ref}
      className="suggestions-wrap"
      exit={{ opacity: 0, y: 12, transition: { duration: 0.25 } }}
    >
      <ul className="suggestions" ref={scope}>
        {SUGGESTIONS.map(({ icon: Icon, label }) => (
          <li key={label}>
            <button type="button" className="suggestion" onClick={() => onPick(label)}>
              <Icon size={16} />
              <span>{label}</span>
            </button>
          </li>
        ))}
      </ul>
    </motion.div>
  );
});
