import { Brain, Folder, Globe, ImagePlus, LibraryBig, Paperclip, PenTool, Telescope } from "lucide-react";
import { FigmaIcon, GithubIcon } from "./BrandIcons";

/**
 * Entries of the composer's "+" menu.
 *  - kind "action": opens a picker/dialog (handled by ChatPage)
 *  - kind "mode":   toggles a chat mode sent to the backend with each message
 */
export const COMPOSER_ACTIONS = [
  { id: "files", kind: "action", label: "Add photos & files", hint: "Upload from computer", icon: Paperclip, tint: "var(--text-2)" },
  { id: "library", kind: "action", label: "Add from library", hint: "Browse and search your files", icon: LibraryBig, tint: "var(--text)" },
  {
    id: "image",
    kind: "mode",
    label: "Create image",
    hint: "Visualize anything",
    icon: ImagePlus,
    tint: "#f5b94a",
    placeholder: "Describe an image to create",
  },
  {
    id: "web_search",
    kind: "mode",
    label: "Web search",
    hint: "Find real-time news and info",
    icon: Globe,
    tint: "#4fa8ff",
    placeholder: "Search the web",
  },
  { id: "project", kind: "action", label: "Work in a project", hint: "Start a chat in a project", icon: Folder, tint: "var(--text-2)" },
  {
    id: "deep_research",
    kind: "mode",
    label: "Deep research",
    hint: "Get a detailed report",
    icon: Telescope,
    tint: "#5b8cff",
    placeholder: "What should I research?",
  },
  { id: "sketch", kind: "action", label: "Sketch", hint: "Draw and attach an image", icon: PenTool, tint: "#36c98e" },
  {
    id: "thinking",
    kind: "mode",
    label: "Thinking",
    hint: "For detailed answers",
    icon: Brain,
    tint: "var(--text-2)",
    placeholder: "Ask anything, I'll think it through",
  },
  {
    id: "github",
    kind: "mode",
    label: "GitHub",
    hint: "Triage PRs, issues, CI, and publish flows",
    icon: GithubIcon,
    tint: "var(--text)",
    placeholder: "e.g. Triage open PRs in owner/repo",
  },
  {
    id: "figma",
    kind: "mode",
    label: "Figma",
    hint: "Create designs, ship to code",
    icon: FigmaIcon,
    tint: null,
    placeholder: "Paste a Figma link or describe a design",
  },
];

export const MODE_BY_ID = Object.fromEntries(
  COMPOSER_ACTIONS.filter((a) => a.kind === "mode").map((a) => [a.id, a])
);
