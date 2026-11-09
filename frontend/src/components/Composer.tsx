import {
  forwardRef,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type CSSProperties,
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUp, CircleAlert, FileText, Folder, Mic, Square, X } from "lucide-react";
import ModelPicker from "./ModelPicker";
import PlusMenu from "./PlusMenu";
import { MODE_BY_ID, type ComposerAction, type ModeId } from "./composerActions";
import { UPLOAD_ACCEPT } from "../lib/api";
import type { Dictation } from "../hooks/useDictation";
import type { ComposerAttachment, Placement, Project } from "../types";

/** Imperative handle ChatPage uses to focus the box and open the file picker. */
export interface ComposerHandle {
  focus: () => void;
  pickFiles: (accept?: string) => void;
}

export interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  onFiles: (files: File[]) => void;
  onAction: (action: ComposerAction) => void;
  busy: boolean;
  model: string;
  onModelChange: (id: string) => void;
  dictation: Dictation;
  placement: Placement;
  mode: ModeId | null;
  onClearMode: () => void;
  attachments: ComposerAttachment[];
  onRemoveAttachment: (localId: string) => void;
  project: Project | null;
  onLeaveProject?: () => void;
}

const MAX_HEIGHT = 220;

interface AttachmentChipProps {
  item: ComposerAttachment;
  onRemove: () => void;
}

function AttachmentChip({ item, onRemove }: AttachmentChipProps) {
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
        <img src={item.previewUrl || item.url || undefined} alt={item.name} />
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

const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
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

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (busy) return;
    if (canSend) onSubmit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    } else if (event.key === "Backspace" && !value && mode && event.currentTarget.selectionStart === 0) {
      // Backspace in an empty box drops the mode, like removing a tag.
      onClearMode();
    }
  };

  const onPaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = [...(event.clipboardData?.files || [])];
    if (files.length) {
      event.preventDefault();
      onFiles(files);
    }
  };

  const hasFiles = (event: DragEvent) => [...(event.dataTransfer?.types || [])].includes("Files");

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
              style={modeInfo.tint ? ({ "--mode-tint": modeInfo.tint } as CSSProperties) : undefined}
              initial={{ opacity: 0, scale: 0.85, x: -6 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.85 }}
            >
              <modeInfo.icon size={14} />
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
