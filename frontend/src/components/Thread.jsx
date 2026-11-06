import { memo, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Check, CircleAlert, Copy, Paperclip, Square, Volume2 } from "lucide-react";
import Logo from "./Logo";

/**
 * Prepare model output for Markdown + KaTeX:
 *  - \( … \) → $…$ and \[ … \] → $$…$$ (remark-math only knows dollar syntax)
 *  - drop empty bold artifacts like "** **"
 * Code spans and fenced blocks are left untouched.
 */
function normalizeAnswer(text) {
  const parts = text.split(/(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g);
  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part; // code
      return part
        .replace(/\\\[([\s\S]+?)\\\]/g, (_, math) => `\n$$\n${math.trim()}\n$$\n`)
        .replace(/\\\(([\s\S]+?)\\\)/g, (_, math) => `$${math.trim()}$`)
        .replace(/^[ \t]*\*\*[ \t]*\*\*[ \t]*$/gm, "");
    })
    .join("")
    .trim();
}

// Rough Markdown → speech text for "Read aloud".
function speakable(text) {
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

function Spark({ active }) {
  return (
    <span className={`spark ${active ? "active" : ""}`} aria-hidden="true">
      <Logo size={17} />
    </span>
  );
}

function ToolChip({ tool }) {
  return (
    <motion.div
      className={`tool-chip ${tool.done ? "done" : ""}`}
      initial={{ opacity: 0, y: 6, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
    >
      {tool.done ? <Check size={13} /> : <span className="tool-spinner" />}
      <span>{tool.done ? `${tool.name} complete` : `Using ${tool.name}…`}</span>
    </motion.div>
  );
}

function CopyButton({ text }) {
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

function SpeakButton({ text }) {
  const [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => () => speaking && window.speechSynthesis.cancel(), [speaking]);

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

const markdownComponents = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" />,
};

const remarkPlugins = [remarkGfm, [remarkMath, { singleDollarTextMath: true }]];
const rehypePlugins = [[rehypeKatex, { throwOnError: false, strict: "ignore" }]];

const Message = memo(function Message({ message, index }) {
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
        <div className="bubble">
          {message.file ? (
            <span className="file-chip">
              <Paperclip size={14} /> {message.file}
            </span>
          ) : (
            message.content
          )}
        </div>
      ) : (
        <>
          <Spark active={message.streaming} />
          <div className="assistant-body">
            {message.tool && <ToolChip tool={message.tool} />}

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

export default function Thread({ messages }) {
  const scrollRef = useRef(null);
  const stickRef = useRef(true);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  // Follow the stream unless the user has scrolled up to read.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <motion.section
      className="thread"
      ref={scrollRef}
      onScroll={onScroll}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      aria-live="polite"
    >
      <div className="thread-inner">
        <AnimatePresence initial={false}>
          {messages.map((message, index) => (
            <Message key={message.id} message={message} index={index} />
          ))}
        </AnimatePresence>
      </div>
    </motion.section>
  );
}
