import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";
import { Eraser, PenTool, Trash2, Undo2 } from "lucide-react";
import Dialog from "./Dialog";

const COLORS = ["#11141d", "#e5484d", "#f5a524", "#30a46c", "#3d5afe", "#8e4ec6", "#ffffff"];
const SIZES = [3, 6, 12];
const WIDTH = 1200;
const HEIGHT = 800;
const MAX_UNDO = 30;

type Tool = "pen" | "eraser";

interface Point {
  x: number;
  y: number;
}

interface SketchDialogProps {
  open: boolean;
  onClose: () => void;
  onAttach: (file: File) => void | Promise<void>;
}

/** Freehand drawing pad; the result is attached to the chat as a PNG. */
export default function SketchDialog({ open, onClose, onAttach }: SketchDialogProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef<Point | null>(null);
  const history = useRef<ImageData[]>([]);
  const [color, setColor] = useState(COLORS[0]);
  const [size, setSize] = useState(SIZES[1]);
  const [tool, setTool] = useState<Tool>("pen");
  const [dirty, setDirty] = useState(false);
  const [canUndo, setCanUndo] = useState(false);
  const [saving, setSaving] = useState(false);

  const context = () => canvasRef.current?.getContext("2d");

  const reset = useCallback(() => {
    const ctx = context();
    if (!ctx) return;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
    history.current = [];
    setCanUndo(false);
    setDirty(false);
  }, []);

  // Fresh white page each time the dialog opens (after the canvas mounts).
  useEffect(() => {
    if (!open) return undefined;
    const frame = requestAnimationFrame(reset);
    return () => cancelAnimationFrame(frame);
  }, [open, reset]);

  const point = (event: PointerEvent<HTMLCanvasElement>): Point => {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * WIDTH,
      y: ((event.clientY - rect.top) / rect.height) * HEIGHT,
    };
  };

  const onPointerDown = (event: PointerEvent<HTMLCanvasElement>) => {
    const ctx = context();
    if (!ctx) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    history.current.push(ctx.getImageData(0, 0, WIDTH, HEIGHT));
    if (history.current.length > MAX_UNDO) history.current.shift();
    setCanUndo(true);

    const start = point(event);
    drawing.current = start;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = tool === "eraser" ? "#ffffff" : color;
    ctx.lineWidth = (tool === "eraser" ? size * 4 : size) * (WIDTH / event.currentTarget.clientWidth);
    // A dot for single clicks.
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(start.x + 0.01, start.y);
    ctx.stroke();
    setDirty(true);
  };

  const onPointerMove = (event: PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const ctx = context();
    if (!ctx) return;
    const next = point(event);
    ctx.beginPath();
    ctx.moveTo(drawing.current.x, drawing.current.y);
    ctx.lineTo(next.x, next.y);
    ctx.stroke();
    drawing.current = next;
  };

  const endStroke = () => {
    drawing.current = null;
  };

  const undo = () => {
    const snapshot = history.current.pop();
    if (snapshot) context()?.putImageData(snapshot, 0, 0);
    setCanUndo(history.current.length > 0);
    if (!history.current.length) setDirty(false);
  };

  const attach = () => {
    const canvas = canvasRef.current;
    if (!dirty || saving || !canvas) return;
    setSaving(true);
    canvas.toBlob(async (blob) => {
      try {
        if (blob) {
          const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
          await onAttach(new File([blob], `sketch-${stamp}.png`, { type: "image/png" }));
        }
      } finally {
        setSaving(false);
      }
    }, "image/png");
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Sketch"
      subtitle="Draw something and attach it to your message."
      wide
      footer={
        <>
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn primary" onClick={attach} disabled={!dirty || saving}>
            {saving ? "Attaching…" : "Attach sketch"}
          </button>
        </>
      }
    >
      <div className="sketch-toolbar" role="toolbar" aria-label="Drawing tools">
        <div className="segmented">
          <button type="button" className={tool === "pen" ? "on" : ""} onClick={() => setTool("pen")} aria-pressed={tool === "pen"} title="Pen">
            <PenTool size={15} />
          </button>
          <button type="button" className={tool === "eraser" ? "on" : ""} onClick={() => setTool("eraser")} aria-pressed={tool === "eraser"} title="Eraser">
            <Eraser size={15} />
          </button>
        </div>

        <div className="swatches">
          {COLORS.map((c) => (
            <button
              key={c}
              type="button"
              className={`swatch ${c === color && tool === "pen" ? "on" : ""}`}
              style={{ background: c }}
              onClick={() => {
                setColor(c);
                setTool("pen");
              }}
              aria-label={`Colour ${c}`}
              aria-pressed={c === color}
            />
          ))}
        </div>

        <div className="segmented">
          {SIZES.map((s) => (
            <button key={s} type="button" className={s === size ? "on" : ""} onClick={() => setSize(s)} aria-pressed={s === size} title={`Brush ${s}px`}>
              <span className="size-dot" style={{ width: s + 2, height: s + 2 }} />
            </button>
          ))}
        </div>

        <div className="composer-spacer" />
        <button type="button" className="icon-btn" onClick={undo} disabled={!canUndo} aria-label="Undo" title="Undo">
          <Undo2 size={16} />
        </button>
        <button type="button" className="icon-btn" onClick={reset} disabled={!dirty} aria-label="Clear" title="Clear">
          <Trash2 size={16} />
        </button>
      </div>

      <canvas
        ref={canvasRef}
        className={`sketch-canvas ${tool}`}
        width={WIDTH}
        height={HEIGHT}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endStroke}
        onPointerCancel={endStroke}
        aria-label="Drawing canvas"
      />
    </Dialog>
  );
}
