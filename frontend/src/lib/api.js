// Thin client for the DevGPT FastAPI backend.
// Every request carries X-Client-Id because the backend scopes
// conversations per browser client (REQUIRE_CLIENT_ID=true).

const CLIENT_KEY = "devgpt.client_id";
const THREAD_KEY = "thread_id"; // kept from the previous frontend
const MODEL_KEY = "selected_model"; // kept from the previous frontend

export const MODELS = [
  { id: "openai/gpt-oss-120b", family: "GPT-OSS", size: "120B", hint: "Most capable" },
  { id: "openai/gpt-oss-20b", family: "GPT-OSS", size: "20B", hint: "Faster" },
  { id: "qwen/qwen3.8-27b", family: "Qwen 3.8", size: "27B", hint: "Balanced" },
];

export const UPLOAD_ACCEPT = ".pdf,.docx,.txt,.md,.py,.csv";

function safeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) — keep going in memory */
  }
}

export function uuid() {
  if (globalThis.crypto?.randomUUID) {
    try {
      return crypto.randomUUID();
    } catch {
      /* insecure context — fall through */
    }
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

let clientId = safeGet(CLIENT_KEY);
if (!clientId) {
  clientId = uuid();
  safeSet(CLIENT_KEY, clientId);
}
export const CLIENT_ID = clientId;

export function loadThreadId() {
  let id = safeGet(THREAD_KEY);
  if (!id) {
    id = uuid();
    safeSet(THREAD_KEY, id);
  }
  return id;
}

export function saveThreadId(id) {
  safeSet(THREAD_KEY, id);
}

export function loadModel() {
  const saved = safeGet(MODEL_KEY);
  return MODELS.some((m) => m.id === saved) ? saved : MODELS[0].id;
}

export function saveModel(id) {
  safeSet(MODEL_KEY, id);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-Client-Id": CLIENT_ID, ...(options.headers || {}) },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      message = data.detail?.toString?.() || data.error || data.message || message;
    } catch {
      /* non-JSON error body */
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return response;
}

export async function listConversations() {
  const response = await request("/conversations");
  const data = await response.json();
  return data.conversations || [];
}

export async function getHistory(threadId) {
  const response = await request(`/history/${encodeURIComponent(threadId)}`);
  const data = await response.json();
  return data.messages || [];
}

export async function deleteConversation(threadId) {
  await request(`/conversations/${encodeURIComponent(threadId)}`, { method: "DELETE" });
}

export async function uploadDocument(file, threadId) {
  const form = new FormData();
  form.append("file", file);
  form.append("thread_id", threadId);

  const response = await fetch("/upload", {
    method: "POST",
    body: form,
    headers: { "X-Client-Id": CLIENT_ID },
  });

  let data = {};
  try {
    data = await response.json();
  } catch {
    /* fall through to generic error */
  }

  if (!response.ok || !data.success) {
    throw new Error(data.message || data.error || `Upload failed (${response.status})`);
  }
  return data;
}

function parseSSEPart(part) {
  const lines = part.split(/\r?\n/).filter((line) => line.trim().startsWith("data:"));
  if (!lines.length) return null;

  const json = lines.map((line) => line.replace(/^\s*data:\s?/, "")).join("\n").trim();
  if (!json || json === "[DONE]") return null;

  try {
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/**
 * Stream a chat reply. Calls onEvent for each `{token}`, `{error}` or `{done}`
 * payload. Resolves when the stream ends; rejects on network / HTTP failure.
 */
export async function streamChat({ message, threadId, model, signal, onEvent }) {
  const response = await request("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId, model }),
    signal,
  });

  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() || "";

    for (const part of parts) {
      const data = parseSSEPart(part);
      if (data) onEvent(data);
    }
  }

  // The final event may not be terminated by a blank line.
  buffer += decoder.decode();
  if (buffer.trim()) {
    const data = parseSSEPart(buffer);
    if (data) onEvent(data);
  }
}

export function sendHeartbeat() {
  return request("/sessions/heartbeat", { method: "POST" }).catch(() => {});
}

export function sendCloseBeacon() {
  const url = `/sessions/close?client_id=${encodeURIComponent(CLIENT_ID)}`;
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url);
  } else {
    fetch(url, { method: "POST", keepalive: true }).catch(() => {});
  }
}

// Mirrors the previous frontend's heuristic, used only to show a
// "Using <tool>…" indicator while waiting for the first token.
export function detectLikelyTool(message) {
  const text = message.toLowerCase();

  if (/remember that|save this|store this|keep in memory|memorize/.test(text)) return "Memory";
  if (/what do you remember|recall|my memory|remember about me/.test(text)) return "Memory recall";
  if (/document|pdf|file|uploaded|summarize|summary|according to|based on/.test(text)) return "Document search";
  if (
    /latest|current|today|now|recent|news|search web|web search|internet|online|price|version|update|who is|what is happening|trending|release|new model/.test(
      text
    )
  )
    return "Web search";
  if (/(\d+\s*[+\-*/×÷]\s*\d+)|calculate|calculation|math|solve/.test(text)) return "Calculator";
  return null;
}
