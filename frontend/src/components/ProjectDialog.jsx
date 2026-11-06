import { useEffect, useState } from "react";
import { ChevronRight, Folder, FolderPlus, Pencil, Trash2 } from "lucide-react";
import Dialog from "./Dialog";

const EMPTY = { name: "", instructions: "" };

/**
 * Pick a project to start a chat in, or create / edit / delete one.
 * Project instructions apply to every chat inside the project.
 */
export default function ProjectDialog({ open, onClose, projects, activeProjectId, onStart, onCreate, onUpdate, onDelete }) {
  const [editing, setEditing] = useState(null); // null | "new" | project id
  const [draft, setDraft] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);

  useEffect(() => {
    if (!open) {
      setEditing(null);
      setDraft(EMPTY);
      setConfirmDelete(null);
    } else if (projects.length === 0) {
      setEditing("new");
    }
  }, [open, projects.length]);

  const startEdit = (project) => {
    setEditing(project ? project.id : "new");
    setDraft(project ? { name: project.name, instructions: project.instructions } : EMPTY);
  };

  const save = async (event) => {
    event.preventDefault();
    const name = draft.name.trim();
    if (!name || saving) return;
    setSaving(true);
    try {
      if (editing === "new") {
        const created = await onCreate(name, draft.instructions.trim());
        if (created) onStart(created);
      } else {
        await onUpdate(editing, { name, instructions: draft.instructions.trim() });
        setEditing(null);
      }
    } finally {
      setSaving(false);
    }
  };

  const form = (
    <form className="project-form" onSubmit={save}>
      <label>
        <span>Project name</span>
        <input
          data-autofocus
          value={draft.name}
          maxLength={60}
          onChange={(event) => setDraft((d) => ({ ...d, name: event.target.value }))}
          placeholder="e.g. Portfolio website"
          required
        />
      </label>
      <label>
        <span>
          Instructions <small>optional · applied to every chat in this project</small>
        </span>
        <textarea
          value={draft.instructions}
          maxLength={4000}
          rows={5}
          onChange={(event) => setDraft((d) => ({ ...d, instructions: event.target.value }))}
          placeholder="e.g. We use React + Tailwind. Keep answers short and include code."
        />
      </label>
      <div className="form-actions">
        {projects.length > 0 && (
          <button type="button" className="btn ghost" onClick={() => setEditing(null)}>
            Back
          </button>
        )}
        <button type="submit" className="btn primary" disabled={!draft.name.trim() || saving}>
          {saving ? "Saving…" : editing === "new" ? "Create and start chat" : "Save"}
        </button>
      </div>
    </form>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={editing === "new" ? "New project" : editing ? "Edit project" : "Projects"}
      subtitle={editing ? null : "Start a chat inside a project to share its instructions."}
    >
      {editing ? (
        form
      ) : (
        <>
          <ul className="project-list">
            {projects.map((project) => (
              <li key={project.id} className={project.id === activeProjectId ? "active" : ""}>
                <button type="button" className="project-open" onClick={() => onStart(project)}>
                  <Folder size={17} />
                  <span className="project-text">
                    <span>{project.name}</span>
                    {project.instructions && <small>{project.instructions}</small>}
                  </span>
                  <ChevronRight size={16} className="project-chev" />
                </button>
                <button type="button" className="icon-btn" onClick={() => startEdit(project)} aria-label={`Edit ${project.name}`} title="Edit">
                  <Pencil size={14} />
                </button>
                <button
                  type="button"
                  className={`icon-btn danger ${confirmDelete === project.id ? "confirm" : ""}`}
                  onClick={() => (confirmDelete === project.id ? onDelete(project.id) : setConfirmDelete(project.id))}
                  onBlur={() => setConfirmDelete(null)}
                  aria-label={confirmDelete === project.id ? `Confirm delete ${project.name}` : `Delete ${project.name}`}
                  title={confirmDelete === project.id ? "Click again to delete (chats are kept)" : "Delete"}
                >
                  {confirmDelete === project.id ? "Delete" : <Trash2 size={14} />}
                </button>
              </li>
            ))}
          </ul>
          <button type="button" className="new-project" onClick={() => startEdit(null)}>
            <FolderPlus size={16} />
            New project
          </button>
        </>
      )}
    </Dialog>
  );
}
