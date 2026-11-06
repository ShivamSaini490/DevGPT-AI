import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Composer from "../components/Composer";
import LibraryDialog from "../components/LibraryDialog";
import ProjectDialog from "../components/ProjectDialog";
import Sidebar from "../components/Sidebar";
import SketchDialog from "../components/SketchDialog";
import Thread from "../components/Thread";
import TopBar from "../components/TopBar";
import { Hero, Suggestions } from "../components/Welcome";
import { useDictation } from "../hooks/useDictation";
import {
  IMAGE_ACCEPT,
  MAX_ATTACHMENTS,
  MODELS,
  UPLOAD_ACCEPT,
  attachFromLibrary,
  createProject,
  deleteConversation,
  deleteProject,
  getHistory,
  listConversations,
  listProjects,
  loadModel,
  loadThreadId,
  renameConversation,
  saveModel,
  saveThreadId,
  streamChat,
  toolLabel,
  updateProject,
  uploadFile,
  uuid,
} from "../lib/api";

const SIDEBAR_KEY = "devgpt.sidebar";

const IMAGE_EXTENSIONS = IMAGE_ACCEPT.split(",");
const ALLOWED_EXTENSIONS = UPLOAD_ACCEPT.split(",");

const MODE_STATUS = {
  image: "Creating image…",
  web_search: "Searching the web…",
  deep_research: "Researching…",
  thinking: "Thinking deeply…",
  github: "Working with GitHub…",
  figma: "Working with Figma…",
};

function extensionOf(name) {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

function historyToMessages(history) {
  return history.map((m) => ({
    id: uuid(),
    role: m.role === "user" ? "user" : "assistant",
    content: m.content,
    attachments: m.attachments || [],
    fromHistory: true,
  }));
}

// What to ask when the user sends attachments without typing anything.
function defaultPrompt(attachments) {
  const images = attachments.filter((a) => a.kind === "image").length;
  const docs = attachments.length - images;
  if (images && !docs) return images > 1 ? "Describe these images." : "Describe this image.";
  if (docs && !images) return docs > 1 ? "Summarize these documents." : "Summarize this document.";
  return "Take a look at these files.";
}

const doneAll = (tools) => (tools || []).map((t) => ({ ...t, done: true }));

// Provider errors arrive as e.g. "Error code: 401 - {'error': {'message': 'Invalid API Key', ...}}".
function readableError(raw) {
  const text = String(raw || "Something went wrong.");
  const message = text.match(/['"]message['"]\s*:\s*['"]([^'"]+)['"]/)?.[1];
  const code = text.match(/Error code:\s*(\d{3})/)?.[1];
  if (!message) return text;
  if (code === "401") return `${message}. Check the model API key in backend/.env.`;
  return code ? `${message} (${code})` : message;
}

function initialSidebar() {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "open" && window.innerWidth >= 960;
  } catch {
    return false;
  }
}

export default function ChatPage({ theme, onToggleTheme, introDone, onReady, onBusyChange, onNavigate }) {
  const [threadId, setThreadId] = useState(loadThreadId);
  const [messages, setMessages] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState(loadModel);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [ready, setReady] = useState(false);
  const [toast, setToast] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(initialSidebar);
  const [mode, setMode] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [projects, setProjects] = useState([]);
  // Project chosen for a chat that doesn't exist on the server yet.
  const [pendingProjectId, setPendingProjectId] = useState(null);
  const [dialog, setDialog] = useState(null); // "library" | "project" | "sketch" | null

  const composerRef = useRef(null);
  const dockRef = useRef(null);
  const abortRef = useRef(null);
  const toastTimer = useRef(0);

  const showToast = useCallback((text) => {
    clearTimeout(toastTimer.current);
    setToast(text);
    toastTimer.current = setTimeout(() => setToast(null), 4200);
  }, []);

  const dictation = useDictation((text) => {
    setInput((current) => (current.trim() ? `${current.trim()} ${text}` : text));
  });

  useEffect(() => {
    if (dictation.error) showToast(dictation.error);
  }, [dictation.error, showToast]);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await listConversations());
    } catch {
      /* sidebar just stays as-is */
    }
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await listProjects());
    } catch {
      /* keep the current list */
    }
  }, []);

  const clearAttachments = useCallback(() => {
    setAttachments((list) => {
      list.forEach((a) => a.previewUrl && URL.revokeObjectURL(a.previewUrl));
      return [];
    });
  }, []);

  const openThread = useCallback(
    async (id) => {
      abortRef.current?.abort();
      setThreadId(id);
      saveThreadId(id);
      setPendingProjectId(null);
      clearAttachments();
      try {
        setMessages(historyToMessages(await getHistory(id)));
      } catch (error) {
        setMessages([]);
        if (error.status !== 404) showToast(`Couldn't load this chat: ${error.message}`);
      }
    },
    [showToast, clearAttachments]
  );

  // Initial load: restore the last thread, the conversation list and projects.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [history, list, projectList] = await Promise.allSettled([
        getHistory(threadId),
        listConversations(),
        listProjects(),
      ]);
      if (cancelled) return;

      if (list.status === "fulfilled") setConversations(list.value);
      if (projectList.status === "fulfilled") setProjects(projectList.value);
      if (history.status === "fulfilled") setMessages(historyToMessages(history.value));
      if (list.status === "rejected") {
        showToast("Can't reach the DevGPT server. Is the backend running?");
      }
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_KEY, sidebarOpen ? "open" : "closed");
    } catch {
      /* ignore */
    }
  }, [sidebarOpen]);

  // Composer entrance once the first view is ready.
  useGSAP(
    () => {
      if (!ready || !introDone || !dockRef.current) return;
      gsap.from(dockRef.current.querySelector(".composer"), {
        y: 24,
        opacity: 0,
        scale: 0.98,
        duration: 0.9,
        ease: "power3.out",
        delay: 0.3,
        clearProps: "transform,opacity",
      });
    },
    { dependencies: [ready, introDone] }
  );

  const patchMessage = useCallback((id, patch) => {
    setMessages((list) =>
      list.map((m) => (m.id === id ? { ...m, ...(typeof patch === "function" ? patch(m) : patch) } : m))
    );
  }, []);

  const currentProjectId =
    conversations.find((c) => c.thread_id === threadId)?.project_id || pendingProjectId || null;
  const currentProject = projects.find((p) => p.id === currentProjectId) || null;

  const send = useCallback(async () => {
    const readyFiles = attachments.filter((a) => a.status === "ready");
    if (busy || attachments.some((a) => a.status === "uploading")) return;
    const typed = input.trim();
    if (!typed && !readyFiles.length) return;
    if (dictation.listening) dictation.stop();

    const text = typed || defaultPrompt(readyFiles);
    const assistantId = uuid();
    const modelInfo = MODELS.find((m) => m.id === model);

    setMessages((list) => [
      ...list,
      {
        id: uuid(),
        role: "user",
        content: text,
        attachments: readyFiles.map(({ id, name, kind, url, previewUrl }) => ({ id, name, kind, url, previewUrl })),
      },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
        tools: [],
        reasoning: "",
        model: modelInfo ? `${modelInfo.family} ${modelInfo.size}` : null,
      },
    ]);
    setInput("");
    // Sent files leave the composer; their preview URLs stay alive for the thread.
    setAttachments((list) => list.filter((a) => a.status !== "ready"));
    setBusy(true);
    setStatus(MODE_STATUS[mode] || `Thinking with ${modelInfo?.family} ${modelInfo?.size}…`);

    const controller = new AbortController();
    abortRef.current = controller;
    let firstToken = true;

    try {
      await streamChat({
        message: text,
        threadId,
        model,
        mode,
        attachments: readyFiles.map((a) => a.id),
        projectId: currentProjectId,
        signal: controller.signal,
        onEvent: (data) => {
          // The server withdrew text the model wrote before calling a tool.
          if (data.replace != null) {
            patchMessage(assistantId, { content: data.replace });
          }
          if (data.tool) {
            setStatus(`Using ${toolLabel(data.tool).toLowerCase()}…`);
            patchMessage(assistantId, (m) => {
              const tools = doneAll(m.tools);
              // Repeated calls to the same tool share one chip.
              const last = tools[tools.length - 1];
              if (last && last.name === data.tool) last.done = false;
              else tools.push({ name: data.tool, done: false });
              return { tools };
            });
          }
          if (data.reasoning) {
            patchMessage(assistantId, (m) => ({ reasoning: (m.reasoning || "") + data.reasoning }));
          }
          if (data.token != null) {
            if (firstToken) {
              firstToken = false;
              setStatus("Writing…");
            }
            patchMessage(assistantId, (m) => ({
              content: m.content + data.token,
              tools: doneAll(m.tools),
            }));
          }
          if (data.error) {
            patchMessage(assistantId, (m) => ({
              error: readableError(data.error),
              tools: doneAll(m.tools),
            }));
          }
        },
      });
    } catch (error) {
      if (error.name === "AbortError") {
        patchMessage(assistantId, { stopped: true });
      } else {
        patchMessage(assistantId, { error: error.message || "Something went wrong." });
      }
    } finally {
      patchMessage(assistantId, (m) => ({ streaming: false, tools: doneAll(m.tools) }));
      if (abortRef.current === controller) abortRef.current = null;
      setBusy(false);
      setStatus("");
      setPendingProjectId(null);
      refreshConversations();
      composerRef.current?.focus();
    }
  }, [input, busy, attachments, dictation, model, mode, threadId, currentProjectId, patchMessage, refreshConversations]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  // ---------- Attachments ----------

  const patchAttachment = useCallback((localId, patch) => {
    setAttachments((list) => list.map((a) => (a.localId === localId ? { ...a, ...patch } : a)));
  }, []);

  /** Upload picked, pasted, dropped or sketched files and show them as chips. */
  const addFiles = useCallback(
    (files, origin = "upload") => {
      const room = MAX_ATTACHMENTS - attachments.length;
      if (room <= 0) {
        showToast(`You can attach up to ${MAX_ATTACHMENTS} files per message.`);
        return;
      }
      const accepted = files.filter((file) => {
        const ok = ALLOWED_EXTENSIONS.includes(extensionOf(file.name));
        if (!ok) showToast(`${file.name}: unsupported file type.`);
        return ok;
      });
      if (accepted.length > room) showToast(`Only the first ${room} file(s) were attached.`);

      accepted.slice(0, room).forEach(async (file) => {
        const localId = uuid();
        const kind = IMAGE_EXTENSIONS.includes(extensionOf(file.name)) ? "image" : "document";
        setAttachments((list) => [
          ...list,
          {
            localId,
            name: file.name,
            kind,
            status: "uploading",
            previewUrl: kind === "image" ? URL.createObjectURL(file) : null,
          },
        ]);
        try {
          const saved = await uploadFile(file, threadId, { origin, projectId: currentProjectId });
          patchAttachment(localId, { status: "ready", id: saved.id, url: saved.url, name: saved.name });
          refreshConversations();
        } catch (error) {
          patchAttachment(localId, { status: "error", error: error.message });
          showToast(`${file.name}: ${error.message}`);
        }
      });
    },
    [attachments.length, threadId, currentProjectId, patchAttachment, refreshConversations, showToast]
  );

  const removeAttachment = useCallback((localId) => {
    setAttachments((list) => {
      const item = list.find((a) => a.localId === localId);
      if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
      return list.filter((a) => a.localId !== localId);
    });
  }, []);

  const pickFromLibrary = useCallback(
    async (file) => {
      setDialog(null);
      if (attachments.length >= MAX_ATTACHMENTS) {
        showToast(`You can attach up to ${MAX_ATTACHMENTS} files per message.`);
        return;
      }
      const localId = uuid();
      setAttachments((list) => [
        ...list,
        { localId, name: file.name, kind: file.kind, status: "uploading", url: file.kind === "image" ? file.url : null },
      ]);
      try {
        const copy = await attachFromLibrary(file.id, threadId, currentProjectId);
        patchAttachment(localId, { status: "ready", id: copy.id, url: copy.url });
        refreshConversations();
      } catch (error) {
        patchAttachment(localId, { status: "error", error: error.message });
        showToast(`Couldn't attach ${file.name}: ${error.message}`);
      }
      composerRef.current?.focus();
    },
    [attachments.length, threadId, currentProjectId, patchAttachment, refreshConversations, showToast]
  );

  const attachSketch = useCallback(
    (file) => {
      setDialog(null);
      addFiles([file], "sketch");
      composerRef.current?.focus();
    },
    [addFiles]
  );

  // ---------- Chats & projects ----------

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    if (dictation.listening) dictation.stop();
    const id = uuid();
    setThreadId(id);
    saveThreadId(id);
    setMessages([]);
    setInput("");
    setMode(null);
    setPendingProjectId(null);
    clearAttachments();
    if (window.innerWidth < 960) setSidebarOpen(false);
    requestAnimationFrame(() => composerRef.current?.focus());
  }, [dictation, clearAttachments]);

  const newChatInProject = useCallback(
    (project) => {
      newChat();
      setPendingProjectId(project.id);
      setDialog(null);
    },
    [newChat]
  );

  const onComposerAction = useCallback(
    (action) => {
      if (action.kind === "mode") {
        setMode((current) => (current === action.id ? null : action.id));
        composerRef.current?.focus();
        return;
      }
      if (action.id === "files") {
        composerRef.current?.pickFiles();
      } else if (action.id === "project") {
        refreshProjects();
        setDialog("project");
      } else {
        setDialog(action.id); // library | sketch
      }
    },
    [refreshProjects]
  );

  const addProject = useCallback(
    async (name, instructions) => {
      try {
        const project = await createProject(name, instructions);
        setProjects((list) => [project, ...list]);
        return project;
      } catch (error) {
        showToast(`Couldn't create project: ${error.message}`);
        return null;
      }
    },
    [showToast]
  );

  const editProject = useCallback(
    async (id, patch) => {
      try {
        const saved = await updateProject(id, patch);
        setProjects((list) => list.map((p) => (p.id === id ? saved : p)));
      } catch (error) {
        showToast(`Couldn't save project: ${error.message}`);
      }
    },
    [showToast]
  );

  const removeProject = useCallback(
    async (id) => {
      try {
        await deleteProject(id);
        setProjects((list) => list.filter((p) => p.id !== id));
        if (pendingProjectId === id) setPendingProjectId(null);
        refreshConversations();
      } catch (error) {
        showToast(`Couldn't delete project: ${error.message}`);
      }
    },
    [pendingProjectId, refreshConversations, showToast]
  );

  const selectThread = useCallback(
    async (id) => {
      if (window.innerWidth < 960) setSidebarOpen(false);
      if (id === threadId) return;
      await openThread(id);
    },
    [openThread, threadId]
  );

  const removeThread = useCallback(
    async (id) => {
      try {
        await deleteConversation(id);
        setConversations((list) => list.filter((c) => c.thread_id !== id));
        if (id === threadId) newChat();
      } catch (error) {
        showToast(`Couldn't delete chat: ${error.message}`);
      }
    },
    [threadId, newChat, showToast]
  );

  const renameThread = useCallback(
    async (id, title) => {
      const previous = conversations.find((c) => c.thread_id === id)?.title;
      // Optimistic: show the new name right away.
      setConversations((list) => list.map((c) => (c.thread_id === id ? { ...c, title } : c)));
      try {
        const saved = await renameConversation(id, title);
        setConversations((list) => list.map((c) => (c.thread_id === id ? { ...c, title: saved.title } : c)));
      } catch (error) {
        setConversations((list) => list.map((c) => (c.thread_id === id ? { ...c, title: previous } : c)));
        showToast(`Couldn't rename chat: ${error.message}`);
      }
    },
    [conversations, showToast]
  );

  // Esc stops generation (dialogs handle their own Esc first).
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape" && abortRef.current) abortRef.current.abort();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Report state up to the app shell (splash gate, background activity).
  useEffect(() => {
    if (ready) onReady?.();
  }, [ready, onReady]);

  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  // Stop any in-flight stream when leaving the chat route.
  useEffect(() => () => abortRef.current?.abort(), []);

  const empty = messages.length === 0;

  return (
    <div className="app" data-sidebar={sidebarOpen ? "open" : "closed"}>
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        activeId={threadId}
        onSelect={selectThread}
        onDelete={removeThread}
        onRename={renameThread}
        onNewChat={newChat}
        projects={projects}
        activeProjectId={currentProjectId}
        onNewChatInProject={newChatInProject}
        onManageProjects={() => {
          refreshProjects();
          setDialog("project");
        }}
      />

      <div className="shell" data-intro={introDone ? "done" : "playing"}>
        <TopBar
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen((o) => !o)}
          onNewChat={newChat}
          theme={theme}
          onToggleTheme={onToggleTheme}
          onHome={() => onNavigate("/")}
          status={status}
        />

        <main className={`stage ${empty ? "is-empty" : "is-chat"}`}>
          {ready && introDone && (
            <>
              {!empty && <Thread messages={messages} />}

              <AnimatePresence mode="popLayout">{empty && <Hero key="hero" />}</AnimatePresence>

              <motion.div
                ref={dockRef}
                layout="position"
                className="dock"
                transition={{ type: "spring", stiffness: 260, damping: 32 }}
              >
                <Composer
                  ref={composerRef}
                  value={input}
                  onChange={setInput}
                  onSubmit={send}
                  onStop={stop}
                  onFiles={addFiles}
                  onAction={onComposerAction}
                  busy={busy}
                  model={model}
                  onModelChange={(id) => {
                    setModel(id);
                    saveModel(id);
                  }}
                  dictation={dictation}
                  placement={empty ? "down" : "up"}
                  mode={mode}
                  onClearMode={() => setMode(null)}
                  attachments={attachments}
                  onRemoveAttachment={removeAttachment}
                  project={currentProject}
                  onLeaveProject={pendingProjectId ? () => setPendingProjectId(null) : undefined}
                />
                {!empty && <p className="footnote">DevGPT can make mistakes. Check important info.</p>}
              </motion.div>

              <AnimatePresence mode="popLayout">
                {empty && (
                  <Suggestions
                    key="suggestions"
                    onPick={(text) => {
                      setInput(text);
                      composerRef.current?.focus();
                    }}
                  />
                )}
              </AnimatePresence>
            </>
          )}
        </main>
      </div>

      <LibraryDialog open={dialog === "library"} onClose={() => setDialog(null)} onPick={pickFromLibrary} />
      <SketchDialog open={dialog === "sketch"} onClose={() => setDialog(null)} onAttach={attachSketch} />
      <ProjectDialog
        open={dialog === "project"}
        onClose={() => setDialog(null)}
        projects={projects}
        activeProjectId={currentProjectId}
        onStart={newChatInProject}
        onCreate={addProject}
        onUpdate={editProject}
        onDelete={removeProject}
      />

      <div className="toast-layer">
        <AnimatePresence>
          {toast && (
            <motion.div
              className="toast"
              role="alert"
              initial={{ opacity: 0, y: -12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -12, scale: 0.96 }}
              onClick={() => setToast(null)}
            >
              {toast}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
