import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { MessageSquare, PanelLeftClose, Pencil, SquarePen, Trash2 } from "lucide-react";
import Logo from "./Logo";
import { MAX_TITLE_LENGTH } from "../lib/api";

function ConversationItem({ conversation, active, onSelect, onDelete, onRename }) {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef(null);
  const editingRef = useRef(false); // guards against Enter + blur saving twice
  const title = conversation.title || "New chat";

  const startEditing = () => {
    setDraft(title);
    editingRef.current = true;
    setEditing(true);
  };

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const finish = (save) => {
    if (!editingRef.current) return;
    editingRef.current = false;
    setEditing(false);
    const next = draft.trim().slice(0, MAX_TITLE_LENGTH);
    if (save && next && next !== title) onRename(next);
  };

  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8, height: 0 }}
      className={`conv ${active ? "active" : ""} ${editing ? "editing" : ""}`}
    >
      {/* Chat icon at rest; turns into a rename (pencil) button on hover. */}
      <button
        type="button"
        className="conv-icon"
        onClick={startEditing}
        aria-label={`Rename "${title}"`}
        title="Rename"
        tabIndex={editing ? -1 : 0}
      >
        <MessageSquare size={14} className="ic-chat" />
        <Pencil size={13} className="ic-edit" />
      </button>

      {editing ? (
        <input
          ref={inputRef}
          className="conv-input"
          value={draft}
          maxLength={MAX_TITLE_LENGTH}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              finish(true);
            } else if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              finish(false);
            }
          }}
          onBlur={() => finish(true)}
          aria-label="Chat name"
        />
      ) : (
        <button
          type="button"
          className="conv-main"
          onClick={onSelect}
          onDoubleClick={startEditing}
          title={`${title} (double-click to rename)`}
        >
          <span>{title}</span>
        </button>
      )}

      {!editing && (
        <button
          type="button"
          className={`conv-delete ${confirming ? "confirm" : ""}`}
          onClick={() => (confirming ? onDelete() : setConfirming(true))}
          onBlur={() => setConfirming(false)}
          aria-label={confirming ? "Confirm delete" : "Delete chat"}
          title={confirming ? "Click again to delete" : "Delete chat"}
        >
          {confirming ? "Delete" : <Trash2 size={14} />}
        </button>
      )}
    </motion.li>
  );
}

export default function Sidebar({
  open,
  onClose,
  conversations,
  activeId,
  onSelect,
  onDelete,
  onRename,
  onNewChat,
}) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="sidebar-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="sidebar"
            initial={{ x: -300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -300, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 38 }}
            aria-label="Chat history"
          >
            <div className="sidebar-head">
              <span className="wordmark">
                <Logo size={26} />
                DevGPT
              </span>
              <button type="button" className="icon-btn" onClick={onClose} aria-label="Close sidebar">
                <PanelLeftClose size={18} />
              </button>
            </div>

            <button type="button" className="new-chat" onClick={onNewChat}>
              <SquarePen size={16} />
              New chat
            </button>

            <div className="sidebar-label">Recent</div>
            <ul className="conv-list">
              <AnimatePresence initial={false}>
                {conversations.map((conversation) => (
                  <ConversationItem
                    key={conversation.thread_id}
                    conversation={conversation}
                    active={conversation.thread_id === activeId}
                    onSelect={() => onSelect(conversation.thread_id)}
                    onDelete={() => onDelete(conversation.thread_id)}
                    onRename={(title) => onRename(conversation.thread_id, title)}
                  />
                ))}
              </AnimatePresence>
              {conversations.length === 0 && <li className="conv-empty">No chats yet</li>}
            </ul>

            <p className="sidebar-foot">Chats are cleared shortly after you close this tab.</p>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
