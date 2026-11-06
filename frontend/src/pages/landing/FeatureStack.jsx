import { ArrowRight, Check, CloudSun, FileText, Globe } from "lucide-react";
import Link from "../../components/Link";
import { MODELS } from "../../lib/api";

// Facts below come from the backend: app/tools, app/rag/service.py
// (chunk 900 / overlap 150) and app/core/config.py (3072-dim Gemini embeddings).

function SkeletonLines({ widths }) {
  return (
    <div className="skel">
      {widths.map((w, i) => (
        <span key={i} style={{ width: `${w}%` }} />
      ))}
    </div>
  );
}

function LiveDataCard() {
  return (
    <div className="fs-card fs-light">
      <div className="fs-window">
        <div className="fs-prompt">What's the weather in Pune right now, and any news on new open models?</div>
        <div className="fs-chips">
          <span className="fs-chip">
            <CloudSun size={13} /> Live weather <Check size={12} />
          </span>
          <span className="fs-chip">
            <Globe size={13} /> Web search <Check size={12} />
          </span>
        </div>
        <SkeletonLines widths={[92, 84, 88, 60]} />
        <p className="fs-note">Based on web search results.</p>
      </div>
    </div>
  );
}

function DocumentsCard() {
  return (
    <div className="fs-card fs-terminal force-dark">
      <div className="term-bar">
        <span />
        <span />
        <span />
        <em>document ingestion</em>
      </div>
      <pre className="term">
        <span className="t-dim">$</span> upload <span className="t-accent">lecture-notes.pdf</span>
        {"\n"}
        <span className="t-ok">✓</span> loaded{"     "}pdf → text
        {"\n"}
        <span className="t-ok">✓</span> split{"      "}chunks of 900 chars, 150 overlap
        {"\n"}
        <span className="t-ok">✓</span> embedded{"   "}gemini-embedding-001 · 3072 dims
        {"\n"}
        <span className="t-ok">✓</span> stored{"     "}postgres + pgvector
        {"\n\n"}
        <span className="t-dim">›</span> <span className="t-accent">"Explain section 2 like I'm new to it"</span>
        {"\n"}
        <span className="t-ok">✓</span> search_uploaded_documents
        <span className="t-caret" />
      </pre>
    </div>
  );
}

function MemoryCard() {
  return (
    <div className="fs-card fs-light">
      <div className="fs-window">
        <div className="fs-prompt right">Remember that I prefer concise answers.</div>
        <div className="fs-chips">
          <span className="fs-chip">
            remember_this <Check size={12} />
          </span>
        </div>
        <SkeletonLines widths={[64]} />
        <div className="fs-divider" />
        <div className="fs-prompt right">What do you know about how I like answers?</div>
        <div className="fs-chips">
          <span className="fs-chip">
            recall_memory <Check size={12} />
          </span>
        </div>
        <SkeletonLines widths={[78, 46]} />
      </div>
    </div>
  );
}

function ModelsCard() {
  return (
    <div className="fs-card fs-orb force-dark">
      <div className="orb" aria-hidden="true" />
      <div className="orb-label">
        <span>Streaming replies</span>
        <div className="orb-models">
          {MODELS.map((m) => (
            <span key={m.id}>
              {m.family} <em>{m.size}</em>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

const ITEMS = [
  {
    kicker: "Live data",
    title: "Search the live web",
    body: "News, releases and other time-sensitive questions go to Tavily web search. Weather and stock quotes have their own tools, so current answers aren't guessed.",
    Card: LiveDataCard,
  },
  {
    kicker: "Documents",
    title: "Chat with your files",
    body: "Upload PDF, DOCX, TXT, MD, PY or CSV files up to 10 MB. DevGPT splits them into chunks, embeds them with Gemini and finds the right passages with pgvector.",
    icon: FileText,
    Card: DocumentsCard,
  },
  {
    kicker: "Memory",
    title: "Remembers what matters",
    body: "State a lasting preference once and DevGPT saves it. Before answering questions about you, it checks its memory first.",
    Card: MemoryCard,
  },
  {
    kicker: "Models",
    title: "Fast models, your choice",
    body: "GPT-OSS 120B, GPT-OSS 20B or Qwen 3.8 27B. Answers stream token by token, and you can switch models from the chat box at any time.",
    Card: ModelsCard,
    cta: true,
  },
];

export default function FeatureStack({ onNavigate }) {
  return (
    <section className="fstack" id="features">
      {ITEMS.map(({ kicker, title, body, Card, cta }, i) => (
        <div className="fs-row" key={title} style={{ "--i": i }}>
          <div className="fs-text">
            <span className="l-kicker">{kicker}</span>
            <h3>{title}</h3>
            <p>{body}</p>
            {cta && (
              <Link to="/chat" onNavigate={onNavigate} className="btn btn-ghost btn-sm fs-cta">
                Try it in chat <ArrowRight size={14} />
              </Link>
            )}
          </div>
          <div className="fs-sticky">
            <Card />
          </div>
        </div>
      ))}
    </section>
  );
}
