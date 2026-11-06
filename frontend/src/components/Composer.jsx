import { forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUp, CircleAlert, FileText, Folder, Mic, Square, X } from "lucide-react";
import ModelPicker from "./ModelPicker";
import PlusMenu from "./PlusMenu";
import { MODE_BY_ID } from "./composerActions";
import { UPLOAD_ACCEPT } from "../lib/api";

const MAX_HEIGHT = 220;

function AttachmentChip({ item, onRemove }) {
  const isImage = item.kind === "image";
  return (
    <motion.li
      layout
      className={`attach-chip ${item.status} ${isImage ? "image" : "doc"}`}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      title={item.error || item.name}
    >
      {isImage ? (
        <img src={item.previewUrl || item.url} alt={item.name} />
      ) : (
        <>
          <span className="attach-doc-icon">
            <FileText size={16} />
          </span>
          <span className="attach-doc-text">
            <span>{item.name}</span>
            <small>{item.status === "error" ? "Failed" : item.status === "uploading" ? "Uploading…" : "Document"}</small>
          </span>
        </>
      )}
      {item.status === "uploading" && <span className="attach-spinner" aria-label="Uploading" />}
      {item.status === "error" && (
        <span className="attach-error" aria-label={item.error}>
          <CircleAlert size={16} />
        </span>
      )}
      <button type="button" className="attach-remove" onClick={onRemove} aria-label={`Remove ${item.name}`}>
        <X size={12} strokeWidth={2.6} />
      </button>
    </motion.li>
  );
}

const Composer = forwardRef(function Composer(
  {
    value,
    onChange,
    onSubmit,
    onStop,
    onFiles,
    onAction,
    busy,
    model,
    onModelChange,
    dictation,
    placement,
    mode,
    onClearMode,
    attachments,
    onRemoveAttachment,
    project,
    onLeaveProject,
  },
  ref
) {
  const textareaRef = useRef(null);
  const fileRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
    pickFiles: (accept) => {
      if (!fileRef.current) return;
      fileRef.current.accept = accept || UPLOAD_ACCEPT;
      fileRef.current.click();
    },
  }));

  // Grow with content up to MAX_HEIGHT.
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  }, [value]);

  const uploading = attachments.some((a) => a.status === "uploading");
  const ready = attachments.some((a) => a.status === "ready");
  const canSend = (value.trim().length > 0 || ready) && !busy && !uploading;
  const modeInfo = mode ? MODE_BY_ID[mode] : null;
  const ModeIcon = modeInfo?.icon;

  const submit = (event) => {
    event?.preventDefault();
    if (busy) return;
    if (canSend) onSubmit();
  };

  const onKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    } else if (event.key === "Backspace" && !value && mode && event.target.selectionStart === 0) {
      // Backspace in an empty box drops the mode, like removing a tag.
      onClearMode();
    }
  };

  const onPaste = (event) => {
    const files = [...(event.clipboardData?.files || [])];
    if (files.length) {
      event.preventDefault();
      onFiles(files);
    }
  };

  const hasFiles = (event) => [...(event.dataTransfer?.types || [])].includes("Files");

  return (
    <form
      className={`composer ${dragging ? "dragging" : ""}`}
      onSubmit={submit}
      onDragEnter={(event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        dragDepth.current += 1;
        setDragging(true);
      }}
      onDragOver={(event) => {
        if (hasFiles(event)) event.preventDefault();
      }}
      onDragLeave={() => {
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (!dragDepth.current) setDragging(false);
      }}
      onDrop={(event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        dragDepth.current = 0;
        setDragging(false);
        onFiles([...event.dataTransfer.files]);
      }}
    >
      <AnimatePresence>
        {dragging && (
          <motion.div className="drop-hint" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            Drop photos or files to attach
          </motion.div>
        )}
      </AnimatePresence>

      {(project || attachments.length > 0) && (
        <div className="composer-top">
          {project && (
            <span className="project-pill" title={`Chats here follow the "${project.name}" project instructions`}>
              <Folder size={13} />
              {project.name}
              {onLeaveProject && (
                <button type="button" onClick={onLeaveProject} aria-label="Start a chat outside this project">
                  <X size={12} />
                </button>
              )}
            </span>
          )}
          {attachments.length > 0 && (
            <ul className="attach-list">
              <AnimatePresence initial={false}>
                {attachments.map((item) => (
                  <AttachmentChip key={item.localId} item={item} onRemove={() => onRemoveAttachment(item.localId)} />
                ))}
              </AnimatePresence>
            </ul>
          )}
        </div>
      )}

      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        onPaste={onPaste}
        placeholder={modeInfo?.placeholder || "Ask DevGPT"}
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
          multiple
          hidden
          onChange={(event) => {
            const files = [...(event.target.files || [])];
            if (files.length) onFiles(files);
            event.target.value = "";
          }}
        />
        <PlusMenu placement={placement} mode={mode} disabled={busy} onAction={onAction} />

        <AnimatePresence mode="popLayout" initial={false}>
          {modeInfo ? (
            <motion.span
              key={modeInfo.id}
              className="mode-pill"
              style={modeInfo.tint ? { "--mode-tint": modeInfo.tint } : undefined}
              initial={{ opacity: 0, scale: 0.85, x: -6 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.85 }}
            >
              <ModeIcon size={14} />
              <span>{modeInfo.label}</span>
              <button type="button" onClick={onClearMode} aria-label={`Turn off ${modeInfo.label}`} title={`Turn off ${modeInfo.label}`}>
                <X size={12} />
              </button>
            </motion.span>
          ) : (
            <motion.span key="hint" className="composer-hint" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              Attach, search, create
            </motion.span>
          )}
        </AnimatePresence>

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
          title={busy ? "Stop generating (Esc)" : uploading ? "Waiting for uploads…" : "Send (Enter)"}
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
