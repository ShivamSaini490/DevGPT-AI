import { useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronRight, Folder, FolderOpen, FolderPlus, MessageSquare, PanelLeftClose, Pencil, Plus, SquarePen, Trash2 } from "lucide-react";
import Logo from "./Logo";
import { MAX_TITLE_LENGTH } from "../lib/api";
import type { Conversation, Project } from "../types";

interface ConversationItemProps {
  conversation: Conversation;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}

function ConversationItem({ conversation, active, onSelect, onDelete, onRename }: ConversationItemProps) {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
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

  const finish = (save: boolean) => {
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

interface ProjectGroupProps {
  project: Project;
  chats: Conversation[];
  active: boolean;
  renderChat: (conversation: Conversation) => ReactNode;
  onNewChatInProject: () => void;
}

function ProjectGroup({ project, chats, active, renderChat, onNewChatInProject }: ProjectGroupProps) {
  const [expanded, setExpanded] = useState(active || chats.length > 0);

  useEffect(() => {
    if (active) setExpanded(true);
  }, [active]);

  return (
    <li className={`project-group ${active ? "active" : ""}`}>
      <div className="project-row">
        <button
          type="button"
          className="project-toggle"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          title={project.instructions || project.name}
        >
          <ChevronRight size={13} className={`project-caret ${expanded ? "open" : ""}`} />
          {expanded ? <FolderOpen size={15} /> : <Folder size={15} />}
          <span>{project.name}</span>
        </button>
        <button
          type="button"
          className="project-add"
          onClick={onNewChatInProject}
          aria-label={`New chat in ${project.name}`}
          title={`New chat in ${project.name}`}
        >
          <Plus size={14} />
        </button>
      </div>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.ul
            className="conv-list nested"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            {chats.map(renderChat)}
            {chats.length === 0 && <li className="conv-empty">No chats yet</li>}
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  conversations: Conversation[];
  activeId: string;
  onSelect: (threadId: string) => void;
  onDelete: (threadId: string) => void;
  onRename: (threadId: string, title: string) => void;
  onNewChat: () => void;
  projects?: Project[];
  activeProjectId: string | null;
  onNewChatInProject: (project: Project) => void;
  onManageProjects: () => void;
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
  projects = [],
  activeProjectId,
  onNewChatInProject,
  onManageProjects,
}: SidebarProps) {
  const projectIds = new Set(projects.map((p) => p.id));
  const loose = conversations.filter((c) => !c.project_id || !projectIds.has(c.project_id));

  const renderChat = (conversation: Conversation) => (
    <ConversationItem
      key={conversation.thread_id}
      conversation={conversation}
      active={conversation.thread_id === activeId}
      onSelect={() => onSelect(conversation.thread_id)}
      onDelete={() => onDelete(conversation.thread_id)}
      onRename={(title) => onRename(conversation.thread_id, title)}
    />
  );

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

            <div className="sidebar-scroll">
              <div className="sidebar-label with-action">
                <span>Projects</span>
                <button type="button" onClick={onManageProjects} aria-label="New or manage projects" title="New or manage projects">
                  <FolderPlus size={14} />
                </button>
              </div>
              {projects.length > 0 ? (
                <ul className="project-groups">
                  {projects.map((project) => (
                    <ProjectGroup
                      key={project.id}
                      project={project}
                      chats={conversations.filter((c) => c.project_id === project.id)}
                      active={project.id === activeProjectId}
                      renderChat={renderChat}
                      onNewChatInProject={() => onNewChatInProject(project)}
                    />
                  ))}
                </ul>
              ) : (
                <button type="button" className="sidebar-ghost" onClick={onManageProjects}>
                  <FolderPlus size={15} />
                  New project
                </button>
              )}

              <div className="sidebar-label">Recent</div>
              <ul className="conv-list">
                <AnimatePresence initial={false}>{loose.map(renderChat)}</AnimatePresence>
                {loose.length === 0 && <li className="conv-empty">No chats yet</li>}
              </ul>
            </div>

            <p className="sidebar-foot">Chats are cleared shortly after you close this tab.</p>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
