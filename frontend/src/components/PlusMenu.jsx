import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Plus } from "lucide-react";
import { COMPOSER_ACTIONS } from "./composerActions";

/** The composer's "+" button and its menu of attachments, tools and modes. */
export default function PlusMenu({ placement = "down", mode, disabled, onAction }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
        rootRef.current?.querySelector(".plus-trigger")?.focus();
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      event.preventDefault();
      const items = [...(menuRef.current?.querySelectorAll(".plus-item") || [])];
      const index = items.indexOf(document.activeElement);
      const next = event.key === "ArrowDown" ? index + 1 : index - 1;
      items[(next + items.length) % items.length]?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey, true);
    // Focus the first entry so the menu is usable from the keyboard.
    requestAnimationFrame(() => menuRef.current?.querySelector(".plus-item")?.focus());
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey, true);
    };
  }, [open]);

  const offset = placement === "up" ? 8 : -8;

  return (
    <div className="plus-menu" ref={rootRef}>
      <button
        type="button"
        className={`icon-btn plus-trigger ${open ? "open" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Add files, tools and modes"
        title="Add files, tools and modes"
        disabled={disabled}
      >
        <Plus size={18} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={menuRef}
            role="menu"
            className={`plus-panel ${placement}`}
            initial={{ opacity: 0, y: offset, scale: 0.97, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: offset, scale: 0.97, filter: "blur(4px)" }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
          >
            {COMPOSER_ACTIONS.map((action) => {
              const Icon = action.icon;
              const active = action.kind === "mode" && action.id === mode;
              return (
                <button
                  key={action.id}
                  type="button"
                  role={action.kind === "mode" ? "menuitemcheckbox" : "menuitem"}
                  aria-checked={action.kind === "mode" ? active : undefined}
                  className={`plus-item ${active ? "active" : ""}`}
                  onClick={() => {
                    setOpen(false);
                    onAction(action);
                  }}
                >
                  <span className="plus-icon" style={action.tint ? { color: action.tint } : undefined}>
                    <Icon size={18} />
                  </span>
                  <span className="plus-label">{action.label}</span>
                  <span className="plus-hint">{action.hint}</span>
                  {active && <Check size={15} className="plus-check" />}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
