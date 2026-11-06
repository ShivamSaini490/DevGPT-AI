import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";

/** Centered modal with backdrop, Esc to close and focus restore. */
export default function Dialog({ open, onClose, title, subtitle, wide, children, footer }) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey, true);
    requestAnimationFrame(() => {
      const target = panelRef.current?.querySelector("[data-autofocus]") || panelRef.current;
      target?.focus();
    });
    return () => {
      document.removeEventListener("keydown", onKey, true);
      previous?.focus?.();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="dialog-layer">
          <motion.div
            className="dialog-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            tabIndex={-1}
            className={`dialog ${wide ? "wide" : ""}`}
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
          >
            <header className="dialog-head">
              <div>
                <h2>{title}</h2>
                {subtitle && <p>{subtitle}</p>}
              </div>
              <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
                <X size={18} />
              </button>
            </header>
            <div className="dialog-body">{children}</div>
            {footer && <footer className="dialog-foot">{footer}</footer>}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
