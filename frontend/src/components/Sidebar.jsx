import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { MessageSquare, PanelLeftClose, SquarePen, Trash2 } from "lucide-react";

function ConversationItem({ conversation, active, onSelect, onDelete }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8, height: 0 }}
      className={`conv ${active ? "active" : ""}`}
    >
      <button type="button" className="conv-main" onClick={onSelect} title={conversation.title}>
        <MessageSquare size={14} />
        <span>{conversation.title || "New chat"}</span>
      </button>
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
    </motion.li>
  );
}

export default function Sidebar({ open, onClose, conversations, activeId, onSelect, onDelete, onNewChat }) {
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
              <span className="wordmark">DevGPT</span>
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
