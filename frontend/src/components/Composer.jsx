import { forwardRef, useImperativeHandle, useLayoutEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUp, Mic, Plus, Square } from "lucide-react";
import ModelPicker from "./ModelPicker";
import { UPLOAD_ACCEPT } from "../lib/api";

const MAX_HEIGHT = 220;

const Composer = forwardRef(function Composer(
  { value, onChange, onSubmit, onStop, onAttach, busy, model, onModelChange, dictation, placement },
  ref
) {
  const textareaRef = useRef(null);
  const fileRef = useRef(null);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
  }));

  // Grow with content up to MAX_HEIGHT.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  }, [value]);

  const canSend = value.trim().length > 0 && !busy;

  const submit = (event) => {
    event?.preventDefault();
    if (busy) return;
    if (canSend) onSubmit();
  };

  const onKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask DevGPT"
        rows={1}
        aria-label="Message DevGPT"
      />

      <AnimatePresence>
        {dictation.listening && (
          <motion.div
            className="interim"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <span className="rec-dot" />
            {dictation.interim || "Listening…"}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="composer-row">
        <input
          ref={fileRef}
          type="file"
          accept={UPLOAD_ACCEPT}
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onAttach(file);
            event.target.value = "";
          }}
        />
        <button
          type="button"
          className="icon-btn"
          onClick={() => fileRef.current?.click()}
          title="Upload a document (PDF, DOCX, TXT, MD, PY, CSV)"
          aria-label="Upload a document"
          disabled={busy}
        >
          <Plus size={18} />
        </button>
        <span className="composer-hint">Add a document</span>

        <div className="composer-spacer" />

        <ModelPicker value={model} onChange={onModelChange} placement={placement} />

        {dictation.supported && (
          <button
            type="button"
            className={`icon-btn mic ${dictation.listening ? "recording" : ""}`}
            onClick={dictation.toggle}
            title={dictation.listening ? "Stop dictation" : "Dictate"}
            aria-label={dictation.listening ? "Stop dictation" : "Dictate"}
            aria-pressed={dictation.listening}
          >
            <Mic size={17} />
          </button>
        )}

        <motion.button
          type={busy ? "button" : "submit"}
          className={`send-btn ${busy ? "stop" : ""}`}
          onClick={busy ? onStop : undefined}
          disabled={!busy && !canSend}
          whileTap={{ scale: 0.9 }}
          aria-label={busy ? "Stop generating" : "Send message"}
          title={busy ? "Stop generating (Esc)" : "Send (Enter)"}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={busy ? "stop" : "send"}
              initial={{ scale: 0.4, opacity: 0, rotate: -45 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 0.4, opacity: 0, rotate: 45 }}
              transition={{ duration: 0.18 }}
              className="send-icon"
            >
              {busy ? <Square size={13} fill="currentColor" /> : <ArrowUp size={18} strokeWidth={2.4} />}
            </motion.span>
          </AnimatePresence>
        </motion.button>
      </div>
    </form>
  );
});

export default Composer;
