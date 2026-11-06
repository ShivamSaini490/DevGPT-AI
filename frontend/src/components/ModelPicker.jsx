import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronDown } from "lucide-react";
import { MODELS } from "../lib/api";

export default function ModelPicker({ value, onChange, placement = "down", disabled }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const current = MODELS.find((m) => m.id === value) || MODELS[0];

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const offset = placement === "up" ? 8 : -8;

  return (
    <div className="model-picker" ref={rootRef}>
      <button
        type="button"
        className="model-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        title={`Model: ${current.id}`}
      >
        <span className="model-family">{current.family}</span>
        <span className="model-size">{current.size}</span>
        <ChevronDown size={14} className={open ? "chev open" : "chev"} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            className={`model-menu ${placement}`}
            initial={{ opacity: 0, y: offset, scale: 0.97, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: offset, scale: 0.97, filter: "blur(4px)" }}
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
          >
            <div className="menu-label">Model</div>
            {MODELS.map((model) => (
              <button
                key={model.id}
                type="button"
                role="menuitemradio"
                aria-checked={model.id === value}
                className="menu-item"
                onClick={() => {
                  onChange(model.id);
                  setOpen(false);
                }}
              >
                <span className="menu-item-text">
                  <span>
                    {model.family} <span className="muted">{model.size}</span>
                  </span>
                  <small>{model.hint}</small>
                </span>
                {model.id === value && <Check size={16} />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
