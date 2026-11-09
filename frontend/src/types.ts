// Shared types for the DevGPT frontend.
// API shapes mirror the FastAPI schemas in backend/app/schemas/.

export type Theme = "light" | "dark";
export type Route = "landing" | "chat";
export type Navigate = (to: string) => void;
/** Which way popovers open: below (empty chat) or above (composer docked at the bottom). */
export type Placement = "up" | "down";

export type FileKind = "image" | "document";
export type FileOrigin = "upload" | "sketch" | "generated";

export interface ModelInfo {
  id: string;
  family: string;
  size: string;
  hint: string;
}

/** ConversationOut */
export interface Conversation {
  thread_id: string;
  title: string;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

/** ProjectOut */
export interface Project {
  id: string;
  name: string;
  instructions: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectPatch {
  name?: string;
  instructions?: string;
}

/** FileOut: a file in the library. */
export interface LibraryFile {
  id: string;
  name: string;
  kind: FileKind;
  mime_type: string;
  size: number;
  origin: FileOrigin | string;
  thread_id: string;
  url: string;
  created_at: string | null;
}

/** Attachment as stored on a history message. */
export interface Attachment {
  id: string;
  name: string;
  kind: FileKind;
  url: string;
}

/** HistoryMessage */
export interface HistoryMessage {
  role: string;
  content: string;
  attachments?: Attachment[];
}

/** StreamEvent: one SSE payload from /chat/stream. */
export interface StreamEvent {
  token?: string | null;
  replace?: string | null;
  tool?: string | null;
  reasoning?: string | null;
  error?: string | null;
  done?: boolean | null;
}

export interface UploadResponse {
  success: boolean;
  message: string;
}

// ---------- Client-side state ----------

export interface ToolCall {
  name: string;
  done: boolean;
  label?: string;
}

/** An attachment shown inside a sent message. */
export interface MessageAttachment {
  id?: string;
  name: string;
  kind: FileKind;
  url?: string | null;
  previewUrl?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachments?: MessageAttachment[];
  fromHistory?: boolean;
  streaming?: boolean;
  tools?: ToolCall[];
  /** Legacy single-tool field from older messages. */
  tool?: ToolCall;
  reasoning?: string;
  model?: string | null;
  error?: string;
  stopped?: boolean;
  /** Legacy: name of a file uploaded as its own message. */
  file?: string;
}

export type AttachmentStatus = "uploading" | "ready" | "error";

/** A file waiting in the composer. */
export interface ComposerAttachment {
  localId: string;
  name: string;
  kind: FileKind;
  status: AttachmentStatus;
  id?: string;
  url?: string | null;
  previewUrl?: string | null;
  error?: string;
}
