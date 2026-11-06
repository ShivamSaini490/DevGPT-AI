import { AnimatePresence, motion } from "motion/react";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      type="button"
      className="icon-btn theme-btn"
      onClick={onToggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      title={theme === "dark" ? "Day mode" : "Night mode"}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme}
          initial={{ rotate: -90, scale: 0.5, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0.5, opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="theme-icon"
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
