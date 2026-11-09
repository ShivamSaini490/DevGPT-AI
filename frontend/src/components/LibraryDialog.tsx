import { useEffect, useState } from "react";
import { FileText, Search } from "lucide-react";
import Dialog from "./Dialog";
import { listLibrary } from "../lib/api";
import type { FileKind, LibraryFile } from "../types";

type Filter = "all" | FileKind;
type LoadState = "idle" | "loading" | "error";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "image", label: "Images" },
  { id: "document", label: "Documents" },
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const ORIGIN_LABEL: Record<string, string> = { sketch: "Sketch", generated: "Generated" };

/** Browse and search files from earlier chats, then attach one to this chat. */
interface LibraryDialogProps {
  open: boolean;
  onClose: () => void;
  onPick: (file: LibraryFile) => void;
}

export default function LibraryDialog({ open, onClose, onPick }: LibraryDialogProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [files, setFiles] = useState<LibraryFile[]>([]);
  const [state, setState] = useState<LoadState>("idle");

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    setState("loading");
    // Debounce typing.
    const timer = setTimeout(async () => {
      try {
        const items = await listLibrary(query);
        if (!cancelled) {
          setFiles(items);
          setState("idle");
        }
      } catch {
        if (!cancelled) setState("error");
      }
    }, query ? 220 : 0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, query]);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setFilter("all");
    }
  }, [open]);

  const visible = filter === "all" ? files : files.filter((f) => f.kind === filter);

  return (
    <Dialog open={open} onClose={onClose} title="Library" subtitle="Files from your chats. Pick one to attach." wide>
      <div className="library-tools">
        <label className="search-field">
          <Search size={16} />
          <input
            data-autofocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search files"
            aria-label="Search files"
          />
        </label>
        <div className="segmented" role="tablist" aria-label="File type">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={filter === f.id ? "on" : ""}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {state === "error" && <p className="dialog-empty">Couldn't load your library.</p>}
      {state !== "error" && visible.length === 0 && (
        <p className="dialog-empty">
          {state === "loading" ? "Loading…" : query ? "No files match your search." : "No files yet. Uploads, sketches and generated images appear here."}
        </p>
      )}

      {visible.length > 0 && (
        <ul className="library-grid">
          {visible.map((file) => (
            <li key={file.id}>
              <button type="button" className="library-item" onClick={() => onPick(file)} title={`Attach ${file.name}`}>
                <span className="library-thumb">
                  {file.kind === "image" ? (
                    <img src={file.url} alt="" loading="lazy" />
                  ) : (
                    <FileText size={26} />
                  )}
                </span>
                <span className="library-name">{file.name}</span>
                <span className="library-meta">
                  {ORIGIN_LABEL[file.origin] || (file.kind === "image" ? "Image" : "Document")} · {formatSize(file.size)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Dialog>
  );
}
