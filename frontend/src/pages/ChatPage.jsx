import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Composer from "../components/Composer";
import Sidebar from "../components/Sidebar";
import Thread from "../components/Thread";
import TopBar from "../components/TopBar";
import { Hero, Suggestions } from "../components/Welcome";
import { useDictation } from "../hooks/useDictation";
import {
  MODELS,
  deleteConversation,
  renameConversation,
  detectLikelyTool,
  getHistory,
  listConversations,
  loadModel,
  loadThreadId,
  saveModel,
  saveThreadId,
  streamChat,
  uploadDocument,
  uuid,
} from "../lib/api";

const SIDEBAR_KEY = "devgpt.sidebar";

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

  const openThread = useCallback(async (id) => {
    abortRef.current?.abort();
    setThreadId(id);
    saveThreadId(id);
    try {
      const history = await getHistory(id);
      setMessages(
        history.map((m) => ({
          id: uuid(),
          role: m.role === "user" ? "user" : "assistant",
          content: m.content,
          fromHistory: true,
        }))
      );
    } catch (error) {
      setMessages([]);
      if (error.status !== 404) showToast(`Couldn't load this chat: ${error.message}`);
    }
  }, [showToast]);

  // Initial load: restore the last thread and the conversation list.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [history, list] = await Promise.allSettled([getHistory(threadId), listConversations()]);
      if (cancelled) return;

      if (list.status === "fulfilled") setConversations(list.value);
      if (history.status === "fulfilled") {
        setMessages(
          history.value.map((m) => ({
            id: uuid(),
            role: m.role === "user" ? "user" : "assistant",
            content: m.content,
            fromHistory: true,
          }))
        );
      }
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

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    if (dictation.listening) dictation.stop();

    const toolName = detectLikelyTool(text);
    const assistantId = uuid();
    const modelInfo = MODELS.find((m) => m.id === model);

    setMessages((list) => [
      ...list,
      { id: uuid(), role: "user", content: text },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
        tool: toolName ? { name: toolName, done: false } : null,
        model: modelInfo ? `${modelInfo.family} ${modelInfo.size}` : null,
      },
    ]);
    setInput("");
    setBusy(true);
    setStatus(toolName ? `Using ${toolName.toLowerCase()}…` : `Thinking with ${modelInfo?.family} ${modelInfo?.size}…`);

    const controller = new AbortController();
    abortRef.current = controller;
    let firstToken = true;

    try {
      await streamChat({
        message: text,
        threadId,
        model,
        signal: controller.signal,
        onEvent: (data) => {
          // The server withdrew text the model wrote before calling a tool.
          if (data.replace != null) {
            patchMessage(assistantId, (m) => ({
              content: data.replace,
              // A tool is about to run, so its badge goes back to "in progress".
              tool: m.tool ? { ...m.tool, done: false } : null,
            }));
          }
          if (data.token != null) {
            if (firstToken) {
              firstToken = false;
              setStatus("Writing…");
            }
            patchMessage(assistantId, (m) => ({
              content: m.content + data.token,
              tool: m.tool ? { ...m.tool, done: true } : null,
            }));
          }
          if (data.error) {
            patchMessage(assistantId, (m) => ({
              error: readableError(data.error),
              tool: m.tool ? { ...m.tool, done: true } : null,
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
      patchMessage(assistantId, (m) => ({
        streaming: false,
        tool: m.tool ? { ...m.tool, done: true } : null,
      }));
      if (abortRef.current === controller) abortRef.current = null;
      setBusy(false);
      setStatus("");
      refreshConversations();
      composerRef.current?.focus();
    }
  }, [input, busy, dictation, model, threadId, patchMessage, refreshConversations]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const attach = useCallback(
    async (file) => {
      const assistantId = uuid();
      setMessages((list) => [
        ...list,
        { id: uuid(), role: "user", content: `Uploaded ${file.name}`, file: file.name },
        {
          id: assistantId,
          role: "assistant",
          content: "",
          streaming: true,
          tool: { name: "Document ingestion", done: false },
        },
      ]);
      setBusy(true);
      setStatus(`Reading ${file.name}…`);

      try {
        const data = await uploadDocument(file, threadId);
        patchMessage(assistantId, {
          content: `${data.message}\n\nYou can now ask questions about this document.`,
        });
        refreshConversations();
      } catch (error) {
        patchMessage(assistantId, { error: error.message });
      } finally {
        patchMessage(assistantId, (m) => ({ streaming: false, tool: { ...m.tool, done: true } }));
        setBusy(false);
        setStatus("");
      }
    },
    [threadId, patchMessage, refreshConversations]
  );

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    if (dictation.listening) dictation.stop();
    const id = uuid();
    setThreadId(id);
    saveThreadId(id);
    setMessages([]);
    setInput("");
    if (window.innerWidth < 960) setSidebarOpen(false);
    requestAnimationFrame(() => composerRef.current?.focus());
  }, [dictation]);

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

  // Esc stops generation.
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

              <AnimatePresence mode="popLayout">
                {empty && <Hero key="hero" />}
              </AnimatePresence>

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
                  onAttach={attach}
                  busy={busy}
                  model={model}
                  onModelChange={(id) => {
                    setModel(id);
                    saveModel(id);
                  }}
                  dictation={dictation}
                  placement={empty ? "down" : "up"}
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
