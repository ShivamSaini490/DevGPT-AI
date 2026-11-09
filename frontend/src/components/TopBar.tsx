import { AnimatePresence, motion } from "motion/react";
import { PanelLeft, SquarePen } from "lucide-react";
import Logo from "./Logo";
import ThemeToggle from "./ThemeToggle";
import type { Theme } from "../types";

interface TopBarProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onNewChat: () => void;
  theme: Theme;
  onToggleTheme: () => void;
  onHome?: () => void;
  status?: string;
}

export default function TopBar({ sidebarOpen, onToggleSidebar, onNewChat, theme, onToggleTheme, onHome, status }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <AnimatePresence initial={false}>
          {!sidebarOpen && (
            <motion.div
              className="topbar-brand"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
            >
              <button type="button" className="icon-btn" onClick={onToggleSidebar} aria-label="Open sidebar">
                <PanelLeft size={18} />
              </button>
              <a
                href="/"
                className="wordmark"
                onClick={(event) => {
                  if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
                  event.preventDefault();
                  onHome?.();
                }}
                title="Back to home"
              >
                <Logo size={26} />
                DevGPT
              </a>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="topbar-center" role="status" aria-live="polite">
        <AnimatePresence>
          {status && (
            <motion.div
              className="status-pill"
              initial={{ opacity: 0, y: -8, filter: "blur(4px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -8, filter: "blur(4px)" }}
            >
              <span className="status-dot" />
              {status}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="topbar-right">
        <button type="button" className="icon-btn" onClick={onNewChat} aria-label="New chat" title="New chat">
          <SquarePen size={17} />
        </button>
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  );
}
