// Thin client for the DevGPT FastAPI backend.
// Every request carries X-Client-Id because the backend scopes
// conversations per browser client (REQUIRE_CLIENT_ID=true).

import type {
  Conversation,
  FileOrigin,
  HistoryMessage,
  LibraryFile,
  ModelInfo,
  Project,
  ProjectPatch,
  StreamEvent,
  UploadResponse,
} from "../types";

const CLIENT_KEY = "devgpt.client_id";
const THREAD_KEY = "thread_id"; // kept from the previous frontend
const MODEL_KEY = "selected_model"; // kept from the previous frontend

export const MODELS: readonly ModelInfo[] = [
  { id: "openai/gpt-oss-120b", family: "GPT-OSS", size: "120B", hint: "Most capable" },
  { id: "openai/gpt-oss-20b", family: "GPT-OSS", size: "20B", hint: "Faster" },
  { id: "qwen/qwen3.8-27b", family: "Qwen 3.8", size: "27B", hint: "Balanced" },
];

export const UPLOAD_ACCEPT = ".pdf,.docx,.txt,.md,.py,.csv,.png,.jpg,.jpeg,.webp,.gif";
export const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.webp,.gif";
export const MAX_ATTACHMENTS = 10;

/** An HTTP error from the backend, carrying the response status. */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Message of any thrown value. */
export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error instanceof Error) return error.message || fallback;
  return typeof error === "string" && error ? error : fallback;
}

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode) — keep going in memory */
  }
}

export function uuid(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
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
export const CLIENT_ID: string = clientId;

export function loadThreadId(): string {
  let id = safeGet(THREAD_KEY);
  if (!id) {
    id = uuid();
    safeSet(THREAD_KEY, id);
  }
  return id;
}

export function saveThreadId(id: string): void {
  safeSet(THREAD_KEY, id);
}

export function loadModel(): string {
  const saved = safeGet(MODEL_KEY);
  return saved && MODELS.some((m) => m.id === saved) ? saved : MODELS[0].id;
}

export function saveModel(id: string): void {
  safeSet(MODEL_KEY, id);
}

interface ErrorBody {
  detail?: unknown;
  error?: string;
  message?: string;
}

async function request(path: string, options: RequestInit = {}): Promise<Response> {
  const response = await fetch(path, {
    ...options,
    headers: { "X-Client-Id": CLIENT_ID, ...(options.headers as Record<string, string> | undefined) },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = (await response.json()) as ErrorBody;
      message = data.detail?.toString?.() || data.error || data.message || message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, response.status);
  }

  return response;
}

async function json<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export async function listConversations(): Promise<Conversation[]> {
  const data = await json<{ conversations?: Conversation[] }>(await request("/conversations"));
  return data.conversations || [];
}

export async function getHistory(threadId: string): Promise<HistoryMessage[]> {
  const data = await json<{ messages?: HistoryMessage[] }>(
    await request(`/history/${encodeURIComponent(threadId)}`)
  );
  return data.messages || [];
}

// Backend trims the title and accepts 1–80 characters.
export const MAX_TITLE_LENGTH = 80;

export async function renameConversation(threadId: string, title: string): Promise<Conversation> {
  const response = await request(`/conversations/${encodeURIComponent(threadId)}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify({ title }),
  });
  return json<Conversation>(response);
}

export async function deleteConversation(threadId: string): Promise<void> {
  await request(`/conversations/${encodeURIComponent(threadId)}`, { method: "DELETE" });
}

// ---------- Files, library & projects ----------

export interface UploadOptions {
  origin?: FileOrigin;
  projectId?: string | null;
}

/** Upload a photo, document or sketch to a chat. Resolves to the file record. */
export async function uploadFile(
  file: File,
  threadId: string,
  { origin = "upload", projectId }: UploadOptions = {}
): Promise<LibraryFile> {
  const form = new FormData();
  form.append("file", file);
  form.append("thread_id", threadId);
  form.append("origin", origin);
  if (projectId) form.append("project_id", projectId);
  return json<LibraryFile>(await request("/files", { method: "POST", body: form }));
}

export async function listLibrary(query = ""): Promise<LibraryFile[]> {
  const params = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";
  const data = await json<{ files?: LibraryFile[] }>(await request(`/files${params}`));
  return data.files || [];
}

export async function attachFromLibrary(
  fileId: string,
  threadId: string,
  projectId?: string | null
): Promise<LibraryFile> {
  const response = await request(`/files/${encodeURIComponent(fileId)}/attach`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ thread_id: threadId, project_id: projectId || null }),
  });
  return json<LibraryFile>(response);
}

export async function listProjects(): Promise<Project[]> {
  const data = await json<{ projects?: Project[] }>(await request("/projects"));
  return data.projects || [];
}

export async function createProject(name: string, instructions = ""): Promise<Project> {
  const response = await request("/projects", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ name, instructions }),
  });
  return json<Project>(response);
}

export async function updateProject(id: string, patch: ProjectPatch): Promise<Project> {
  const response = await request(`/projects/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: JSON_HEADERS,
    body: JSON.stringify(patch),
  });
  return json<Project>(response);
}

export async function deleteProject(id: string): Promise<void> {
  await request(`/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function uploadDocument(file: File, threadId: string): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("thread_id", threadId);

  const response = await fetch("/upload", {
    method: "POST",
    body: form,
    headers: { "X-Client-Id": CLIENT_ID },
  });

  let data: Partial<UploadResponse> & { error?: string } = {};
  try {
    data = await response.json();
  } catch {
    /* fall through to generic error */
  }

  if (!response.ok || !data.success) {
    throw new ApiError(data.message || data.error || `Upload failed (${response.status})`, response.status);
  }
  return data as UploadResponse;
}

function parseSSEPart(part: string): StreamEvent | null {
  const lines = part.split(/\r?\n/).filter((line) => line.trim().startsWith("data:"));
  if (!lines.length) return null;

  const payload = lines.map((line) => line.replace(/^\s*data:\s?/, "")).join("\n").trim();
  if (!payload || payload === "[DONE]") return null;

  try {
    return JSON.parse(payload) as StreamEvent;
  } catch {
    return null;
  }
}

export interface StreamChatOptions {
  message: string;
  threadId: string;
  model: string;
  mode?: string | null;
  attachments?: string[];
  projectId?: string | null;
  signal?: AbortSignal;
  onEvent: (event: StreamEvent) => void;
}

/**
 * Stream a chat reply. Calls onEvent for each `{token}`, `{replace}`, `{tool}`,
 * `{reasoning}`, `{error}` or `{done}` payload. Resolves when the stream ends; rejects on network / HTTP failure.
 */
export async function streamChat({
  message,
  threadId,
  model,
  mode,
  attachments,
  projectId,
  signal,
  onEvent,
}: StreamChatOptions): Promise<void> {
  const response = await request("/chat/stream", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      message,
      thread_id: threadId,
      model,
      mode: mode || null,
      attachments: attachments || [],
      project_id: projectId || null,
    }),
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

export function sendHeartbeat(): Promise<Response | void> {
  return request("/sessions/heartbeat", { method: "POST" }).catch(() => {});
}

export function sendCloseBeacon(): void {
  const url = `/sessions/close?client_id=${encodeURIComponent(CLIENT_ID)}`;
  if (navigator.sendBeacon) {
    navigator.sendBeacon(url);
  } else {
    fetch(url, { method: "POST", keepalive: true }).catch(() => {});
  }
}

// Mirrors the previous frontend's heuristic, used only to show a
// "Using <tool>…" indicator while waiting for the first token.
export function detectLikelyTool(message: string): string | null {
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

// Friendly labels for tool names the backend reports in `{tool}` events.
const TOOL_LABELS: Record<string, string> = {
  vision: "Vision",
  calculator: "Calculator",
  search_uploaded_documents: "Document search",
  remember_this: "Memory",
  recall_memory: "Memory recall",
  tavily_search: "Web search",
  get_live_weather: "Weather",
  get_stock_quote: "Stock quote",
  generate_image: "Image generation",
  github_repo_overview: "GitHub",
  github_list_pull_requests: "GitHub pull requests",
  github_pull_request_details: "GitHub pull request",
  github_list_issues: "GitHub issues",
  github_ci_status: "GitHub CI",
  github_create_issue: "GitHub publish",
  github_add_comment: "GitHub publish",
  figma_get_design: "Figma",
};

export function toolLabel(name: string): string {
  return TOOL_LABELS[name] || name.replace(/_/g, " ");
}
