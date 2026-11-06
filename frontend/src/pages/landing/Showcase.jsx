import { ArrowUp, Check, MessageSquare, Plus, SquarePen } from "lucide-react";
import Logo from "../../components/Logo";

// Illustrative product mock: a DevGPT window inside a large dark stage.
// The calculation shown is real (18% of 2,450 = 441).
export default function Showcase() {
  return (
    <section className="showcase-wrap" aria-label="DevGPT chat preview">
      <div className="showcase force-dark">
        <div className="showcase-glow" aria-hidden="true" />

        <div className="mock" aria-hidden="true">
          <aside className="mock-side">
            <div className="mock-brand">
              <Logo size={18} />
              DevGPT
            </div>
            <div className="mock-new">
              <SquarePen size={13} /> New chat
            </div>
            <div className="mock-label">Recent</div>
            {["Budget maths in INR", "Summarize lecture notes", "Weather before the trip", "Fix my regex"].map(
              (title, i) => (
                <div key={title} className={`mock-conv ${i === 0 ? "active" : ""}`}>
                  <MessageSquare size={12} />
                  {title}
                </div>
              )
            )}
          </aside>

          <div className="mock-main">
            <div className="mock-thread">
              <div className="mock-user sc-user">What's 18% of 2,450? Also remember that I budget in INR.</div>
              <div className="mock-assistant">
                <span className="mock-spark">
                  <Logo size={13} variant="current" />
                </span>
                <div>
                  <div className="mock-chips">
                    <span className="mock-chip sc-chip">
                      <Check size={11} /> Calculator complete
                    </span>
                    <span className="mock-chip sc-chip">
                      <Check size={11} /> Memory complete
                    </span>
                  </div>
                  <p className="mock-answer">
                    {"18% of 2,450 is 441. I'll remember that you budget in INR, so future amounts can be shown in rupees."
                      .split(" ")
                      .map((word, i) => (
                        <span key={i} className="sc-token">
                          {word === "441." ? <strong>441</strong> : word}
                          {word === "441." ? ". " : " "}
                        </span>
                      ))}
                  </p>
                </div>
              </div>
            </div>

            <div className="mock-composer">
              <span className="mock-placeholder">Ask DevGPT</span>
              <div className="mock-row">
                <Plus size={14} />
                <span className="mock-model">
                  GPT-OSS <em>120B</em>
                </span>
                <span className="mock-send">
                  <ArrowUp size={13} />
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
