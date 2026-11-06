import { memo, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, CircleAlert, Copy, Paperclip } from "lucide-react";

function Spark({ active }) {
  return (
    <span className={`spark ${active ? "active" : ""}`} aria-hidden="true">
      <svg viewBox="0 0 32 32" width="18" height="18">
        <defs>
          <linearGradient id="spark-g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--spark-a)" />
            <stop offset="1" stopColor="var(--spark-b)" />
          </linearGradient>
        </defs>
        <path
          fill="url(#spark-g)"
          d="M16 2c1.2 7.4 6.6 12.8 14 14-7.4 1.2-12.8 6.6-14 14-1.2-7.4-6.6-12.8-14-14C9.4 14.8 14.8 9.4 16 2z"
        />
      </svg>
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
      className="msg-action"
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
      title="Copy"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

const markdownComponents = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" />,
};

const Message = memo(function Message({ message, index }) {
  const isUser = message.role === "user";
  const delay = message.fromHistory ? Math.min(index * 0.04, 0.4) : 0;

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

            {message.content ? (
              <div className={`markdown ${message.streaming ? "streaming" : ""}`}>
                <Markdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {message.content}
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

            {!message.streaming && message.content && (
              <div className="msg-actions">
                <CopyButton text={message.content} />
              </div>
            )}
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
