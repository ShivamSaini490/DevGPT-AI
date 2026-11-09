import { memo, useCallback, useEffect, useRef, useState, type WheelEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import Markdown, { type Components, type Options } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { ArrowDown, Check, ChevronDown, CircleAlert, Copy, FileText, Paperclip, Sparkles, Square, Volume2 } from "lucide-react";
import Logo from "./Logo";
import { toolLabel } from "../lib/api";
import type { ChatMessage, MessageAttachment, ToolCall } from "../types";

/**
 * Prepare model output for Markdown + KaTeX:
 *  - \( … \) → $…$ and \[ … \] → $$…$$ (remark-math only knows dollar syntax)
 *  - drop empty bold artifacts like "** **"
 * Code spans and fenced blocks are left untouched.
 */
function normalizeAnswer(text: string): string {
  const parts = text.split(/(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g);
  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part; // code
      return part
        .replace(/\\\[([\s\S]+?)\\\]/g, (_, math: string) => `\n$$\n${math.trim()}\n$$\n`)
        .replace(/\\\(([\s\S]+?)\\\)/g, (_, math: string) => `$${math.trim()}$`)
        .replace(/^[ \t]*\*\*[ \t]*\*\*[ \t]*$/gm, "");
    })
    .join("")
    .trim();
}

// Rough Markdown → speech text for "Read aloud".
function speakable(text: string): string {
  return normalizeAnswer(text)
    .replace(/```[\s\S]*?```/g, " code block. ")
    .replace(/\$\$?([^$]+)\$\$?/g, "$1")
    .replace(/\\times/g, " times ")
    .replace(/\\div/g, " divided by ")
    .replace(/[*_#>`~|\\{}]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function Spark({ active }: { active?: boolean }) {
  return (
    <span className={`spark ${active ? "active" : ""}`} aria-hidden="true">
      <Logo size={17} />
    </span>
  );
}

function ToolChip({ tool }: { tool: ToolCall }) {
  const name = tool.label || toolLabel(tool.name);
  return (
    <motion.div
      className={`tool-chip ${tool.done ? "done" : ""}`}
      initial={{ opacity: 0, y: 6, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
    >
      {tool.done ? <Check size={13} /> : <span className="tool-spinner" />}
      <span>{tool.done ? `${name} complete` : `Using ${name}…`}</span>
    </motion.div>
  );
}

function Reasoning({ text, streaming }: { text: string; streaming?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`reasoning ${open ? "open" : ""}`}>
      <button type="button" className="reasoning-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Sparkles size={13} />
        <span className={streaming ? "thinking" : ""}>{streaming ? "Thinking" : "Thought process"}</span>
        <ChevronDown size={14} className={open ? "chev open" : "chev"} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className="reasoning-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <p>{text}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function UserAttachments({ items }: { items: MessageAttachment[] }) {
  const images = items.filter((a) => a.kind === "image");
  const docs = items.filter((a) => a.kind !== "image");
  return (
    <div className="user-attachments">
      {images.length > 0 && (
        <div className={`user-images count-${Math.min(images.length, 3)}`}>
          {images.map((a) => (
            <a key={a.id || a.url} href={a.url || undefined} target="_blank" rel="noreferrer noopener" title={a.name}>
              <img src={a.previewUrl || a.url || undefined} alt={a.name} loading="lazy" />
            </a>
          ))}
        </div>
      )}
      {docs.map((a) => (
        <a key={a.id || a.name} className="user-doc" href={a.url || undefined} target="_blank" rel="noreferrer noopener" title={`Download ${a.name}`}>
          <FileText size={16} />
          <span>{a.name}</span>
        </a>
      ))}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="card-action"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {
          /* clipboard blocked */
        }
      }}
      aria-label="Copy response"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
      <span>{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

function SpeakButton({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(
    () => () => {
      if (speaking) window.speechSynthesis.cancel();
    },
    [speaking]
  );

  if (!supported) return null;

  const toggle = () => {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(speakable(text));
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    synth.speak(utterance);
    setSpeaking(true);
  };

  return (
    <button type="button" className={`card-action ${speaking ? "on" : ""}`} onClick={toggle} aria-pressed={speaking}>
      {speaking ? <Square size={12} fill="currentColor" /> : <Volume2 size={14} />}
      <span>{speaking ? "Stop" : "Read aloud"}</span>
    </button>
  );
}

const markdownComponents: Components = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" />,
  img: ({ src, alt }) => (
    <a className="md-image" href={src} target="_blank" rel="noreferrer noopener">
      <img src={src} alt={alt || ""} loading="lazy" />
    </a>
  ),
};

const remarkPlugins: Options["remarkPlugins"] = [remarkGfm, [remarkMath, { singleDollarTextMath: true }]];
const rehypePlugins: Options["rehypePlugins"] = [[rehypeKatex, { throwOnError: false, strict: "ignore" }]];

interface MessageProps {
  message: ChatMessage;
  index: number;
}

const Message = memo(function Message({ message, index }: MessageProps) {
  const isUser = message.role === "user";
  const delay = message.fromHistory ? Math.min(index * 0.04, 0.4) : 0;
  const answer = message.content ? normalizeAnswer(message.content) : "";

  return (
    <motion.article
      className={`msg ${isUser ? "user" : "assistant"}`}
      initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1], delay }}
    >
      {isUser ? (
        <div className="user-col">
          {message.attachments && message.attachments.length > 0 && <UserAttachments items={message.attachments} />}
          {(message.file || message.content) && (
            <div className="bubble">
              {message.file ? (
                <span className="file-chip">
                  <Paperclip size={14} /> {message.file}
                </span>
              ) : (
                message.content
              )}
            </div>
          )}
        </div>
      ) : (
        <>
          <Spark active={message.streaming} />
          <div className="assistant-body">
            {((message.tools && message.tools.length > 0) || message.tool) && (
              <div className="tool-chips">
                {(message.tools || (message.tool ? [message.tool] : [])).map((tool, i) => (
                  <ToolChip key={`${tool.name}-${i}`} tool={tool} />
                ))}
              </div>
            )}
            {message.reasoning && <Reasoning text={message.reasoning} streaming={message.streaming && !answer} />}

            <div className={`answer-card ${message.streaming ? "streaming" : ""} ${message.error ? "has-error" : ""}`}>
              {answer ? (
                <div className={`markdown ${message.streaming ? "streaming" : ""}`}>
                  <Markdown
                    remarkPlugins={remarkPlugins}
                    rehypePlugins={rehypePlugins}
                    components={markdownComponents}
                  >
                    {answer}
                  </Markdown>
                </div>
              ) : (
                message.streaming && <div className="thinking">Thinking</div>
              )}

              {message.error && (
                <div className="msg-error" role="alert">
                  <CircleAlert size={15} />
                  <span>{message.error}</span>
                </div>
              )}

              {message.stopped && <div className="msg-note">Stopped</div>}

              {!message.streaming && answer && (
                <div className="card-footer">
                  {message.model && <span className="card-model">{message.model}</span>}
                  <div className="card-actions">
                    <SpeakButton text={answer} />
                    <CopyButton text={answer} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </motion.article>
  );
});

// Within this many px of the bottom counts as "reading the latest".
const STICK_PX = 80;
// Offer "scroll to bottom" once scrolled this far up.
const JUMP_PX = 240;
// Offer "scroll to question" once the latest question is this far above the view.
const QUESTION_PX = 40;
// Breathing room above the question after jumping to it (clears the top fade).
const QUESTION_PAD = 16;
// Share of the remaining distance covered per frame while gliding.
const GLIDE_EASE = 0.18;

type JumpDirection = "up" | "down";

const gapToBottom = (el: HTMLElement) => el.scrollHeight - el.scrollTop - el.clientHeight;
const maxScroll = (el: HTMLElement) => Math.max(0, el.scrollHeight - el.clientHeight);

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function Thread({ messages }: { messages: ChatMessage[] }) {
  const scrollRef = useRef<HTMLElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  // Whether new content should pull the view down.
  const stickRef = useRef(true);
  // rAF id while the view is gliding; 0 when idle.
  const glideRef = useRef(0);
  const countRef = useRef(0);
  const [jump, setJump] = useState<JumpDirection | null>(null);

  const stopGlide = useCallback(() => {
    cancelAnimationFrame(glideRef.current);
    glideRef.current = 0;
  }, []);

  /** Where the latest question sits relative to the top of the view (px), or null. */
  const questionOffset = useCallback((el: HTMLElement): number | null => {
    const questions = innerRef.current?.querySelectorAll<HTMLElement>(".msg.user");
    const last = questions?.[questions.length - 1];
    if (!last) return null;
    return last.getBoundingClientRect().top - el.getBoundingClientRect().top;
  }, []);

  /**
   * Ease the scroll position toward `targetFor(el)` each frame. The target is
   * re-read every frame, so a growing answer is chased smoothly.
   */
  const glide = useCallback(
    (targetFor: (el: HTMLElement) => number) => {
      stopGlide();
      const el = scrollRef.current;
      if (!el) return;
      const target = () => Math.min(maxScroll(el), Math.max(0, targetFor(el)));
      if (prefersReducedMotion()) {
        el.scrollTop = target();
        return;
      }
      const step = () => {
        const diff = target() - el.scrollTop;
        if (Math.abs(diff) <= 1) {
          el.scrollTop = target();
          glideRef.current = 0;
          return;
        }
        const before = el.scrollTop;
        el.scrollTop += Math.sign(diff) * Math.max(Math.abs(diff) * GLIDE_EASE, 2);
        // Stop if the browser refused to move (e.g. clamped at an edge).
        glideRef.current = el.scrollTop === before ? 0 : requestAnimationFrame(step);
      };
      glideRef.current = requestAnimationFrame(step);
    },
    [stopGlide]
  );

  /** Glide to the bottom and keep up with the streaming answer. */
  const follow = useCallback(() => glide(maxScroll), [glide]);

  /** Glide so the latest question sits at the top of the view. */
  const toQuestion = useCallback(() => {
    stickRef.current = false;
    glide((el) => el.scrollTop + (questionOffset(el) ?? 0) - QUESTION_PAD);
  }, [glide, questionOffset]);

  const jumpToBottom = useCallback(() => {
    stopGlide();
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [stopGlide]);

  /** Pick the button: ↓ when away from the bottom, ↑ when the latest question is out of view above. */
  const updateJump = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (gapToBottom(el) > JUMP_PX) {
      setJump("down");
      return;
    }
    const offset = questionOffset(el);
    setJump(offset !== null && offset < -QUESTION_PX ? "up" : null);
  }, [questionOffset]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    updateJump();
    // Our own glide moves the view too; only user scrolling decides stickiness.
    if (!glideRef.current) stickRef.current = gapToBottom(el) < STICK_PX;
  };

  // Any manual scroll takes over from the auto-scroll.
  const onWheel = (event: WheelEvent) => {
    stopGlide();
    if (event.deltaY < 0) stickRef.current = false;
  };

  useEffect(() => {
    const added = messages.length > countRef.current;
    const newest = messages[messages.length - 1];
    countRef.current = messages.length;

    if (newest?.fromHistory) {
      // Opening a saved chat: land on its last message without animating.
      stickRef.current = true;
      jumpToBottom();
    } else {
      // Sending a question always brings the view down to it.
      if (added && messages.slice(-2).some((m) => m.role === "user")) stickRef.current = true;
      if (stickRef.current) follow();
    }
    updateJump();
  }, [messages, follow, jumpToBottom, updateJump]);

  // Content can also grow without a new message (images loading, math rendering).
  useEffect(() => {
    const inner = innerRef.current;
    if (!inner) return undefined;
    const observer = new ResizeObserver(() => {
      if (stickRef.current) follow();
      updateJump();
    });
    observer.observe(inner);
    return () => observer.disconnect();
  }, [follow, updateJump]);

  useEffect(() => stopGlide, [stopGlide]);

  const label = jump === "up" ? "Scroll to your latest question" : "Scroll to bottom";

  return (
    <div className="thread-wrap">
      <motion.section
        className="thread"
        ref={scrollRef}
        onScroll={onScroll}
        onWheel={onWheel}
        onTouchStart={stopGlide}
        onPointerDown={stopGlide}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        aria-live="polite"
      >
        <div className="thread-inner" ref={innerRef}>
          <AnimatePresence initial={false}>
            {messages.map((message, index) => (
              <Message key={message.id} message={message} index={index} />
            ))}
          </AnimatePresence>
        </div>
      </motion.section>

      <AnimatePresence>
        {jump && (
          <motion.button
            type="button"
            className="jump-latest"
            data-direction={jump}
            onClick={() => {
              if (jump === "up") {
                toQuestion();
              } else {
                stickRef.current = true;
                follow();
              }
            }}
            initial={{ opacity: 0, y: 10, scale: 0.85 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.85 }}
            transition={{ type: "spring", stiffness: 420, damping: 30 }}
            aria-label={label}
            title={label}
          >
            {/* One arrow that flips between ↓ and ↑. */}
            <motion.span
              className="jump-icon"
              initial={false}
              animate={{ rotate: jump === "up" ? 180 : 0 }}
              transition={{ type: "spring", stiffness: 380, damping: 26 }}
            >
              <ArrowDown size={18} strokeWidth={2.2} />
            </motion.span>
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
