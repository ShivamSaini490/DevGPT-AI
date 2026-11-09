import { useEffect, useRef } from "react";
import type { Theme } from "../../types";

type RGB = [number, number, number];

interface Dot {
  x: number;
  y: number;
  /** eased intensity 0…1 */
  k: number;
  /** per-dot size variance */
  s: number;
}

/*
  Interactive hero field.
  A jittered grid of tiny dots. Near the (eased) cursor, dots turn into short
  dashes that point away from it, get pushed outward into rippling rings and
  pick up a colour based on their direction from the cursor:
  bottom-left → blue/violet, top-right → red/orange.
*/

const STOPS: [number, RGB][] = [
  [0.0, [79, 107, 255]], // blue
  [0.35, [139, 92, 246]], // violet
  [0.68, [239, 68, 68]], // red
  [1.0, [249, 150, 22]], // orange
];

function paletteAt(t: number): RGB {
  for (let i = 1; i < STOPS.length; i++) {
    const [p1, c1] = STOPS[i];
    const [p0, c0] = STOPS[i - 1];
    if (t <= p1) {
      const k = (t - p0) / (p1 - p0);
      return [c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k, c0[2] + (c1[2] - c0[2]) * k];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

// Pre-baked colour strings so the draw loop doesn't build them per frame.
const LUT = Array.from({ length: 64 }, (_, i) => {
  const [r, g, b] = paletteAt(i / 63);
  return `rgb(${r | 0}, ${g | 0}, ${b | 0})`;
});

const COLOURS = 16;
const LEVELS = 4;
const buckets: number[][] = Array.from({ length: COLOURS * LEVELS }, () => []);

const smooth = (e0: number, e1: number, x: number): number => {
  const t = Math.min(Math.max((x - e0) / (e1 - e0), 0), 1);
  return t * t * (3 - 2 * t);
};

export default function HeroField({ theme }: { theme: Theme }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const themeRef = useRef(theme);
  themeRef.current = theme;

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = canvas?.parentElement;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !host || !ctx) return undefined;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let points: Dot[] = [];
    let raf = 0;
    let running = false;
    let last = performance.now();
    let time = 0;
    let lastPointerAt = -1e9;

    // Cursor: target (raw) and eased position. Starts left of centre.
    const cursor = { x: 0, y: 0, tx: 0, ty: 0, inside: false };

    const build = () => {
      const rect = host.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      const gap = width < 640 ? 26 : 32;
      points = [];
      for (let y = gap / 2; y < height; y += gap) {
        for (let x = gap / 2; x < width; x += gap) {
          points.push({
            x: x + (Math.random() - 0.5) * gap * 0.7,
            y: y + (Math.random() - 0.5) * gap * 0.7,
            k: 0, // eased intensity 0…1
            s: 0.6 + Math.random() * 0.8, // per-dot size variance
          });
        }
      }

      if (!cursor.x && !cursor.y) {
        cursor.x = cursor.tx = width * 0.26;
        cursor.y = cursor.ty = height * 0.42;
      }
    };

    const draw = () => {
      const dark = themeRef.current === "dark";
      const dotColor = dark ? "rgba(255,255,255,0.28)" : "rgba(17,20,29,0.28)";
      const radius = Math.min(Math.max(width, height) * 0.36, 460);
      const inner = radius * 0.14;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.lineCap = "round";

      // Plain dots first in one path (cheap), dashes after.
      ctx.fillStyle = dotColor;
      ctx.beginPath();
      for (const p of points) {
        if (p.k > 0.04) continue;
        const r = 0.55 * p.s;
        ctx.moveTo(p.x + r, p.y);
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      }
      ctx.fill();

      // Dashes are grouped into colour × intensity buckets so a frame needs
      // at most BUCKETS strokes instead of one per dash.
      for (const bucket of buckets) bucket.length = 0;

      for (const p of points) {
        if (p.k <= 0.04) continue;
        const dx = p.x - cursor.x;
        const dy = p.y - cursor.y;
        const d = Math.hypot(dx, dy) || 1;
        const ux = dx / d;
        const uy = dy / d;

        // Push outward, more strongly near the middle of the ring.
        const push = 26 * p.k;
        const cx = p.x + ux * push;
        const cy = p.y + uy * push;
        const half = (3 + 9 * p.k) * p.s * 0.5;

        // Direction → colour: top-right warm, bottom-left cool (screen y is down).
        const t = (ux * 0.7071 - uy * 0.7071 + 1) / 2;
        const colour = Math.round(t * (COLOURS - 1));
        const level = Math.min(LEVELS - 1, Math.floor(p.k * LEVELS));
        buckets[colour * LEVELS + level].push(cx - ux * half, cy - uy * half, cx + ux * half, cy + uy * half);
      }

      for (let i = 0; i < buckets.length; i++) {
        const segs = buckets[i];
        if (!segs.length) continue;
        const k = ((i % LEVELS) + 0.5) / LEVELS;
        ctx.strokeStyle = LUT[Math.round(((i / LEVELS) | 0) * (63 / (COLOURS - 1)))];
        ctx.globalAlpha = Math.min(1, 0.25 + k * 0.9);
        ctx.lineWidth = 1.4 + 1.6 * k;
        ctx.beginPath();
        for (let j = 0; j < segs.length; j += 4) {
          ctx.moveTo(segs[j], segs[j + 1]);
          ctx.lineTo(segs[j + 2], segs[j + 3]);
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      return { radius, inner };
    };

    const update = (dt: number) => {
      time += dt;

      // Idle drift: a slow figure-eight around the resting spot.
      if (!cursor.inside && performance.now() - lastPointerAt > 2500) {
        cursor.tx = width * (0.26 + Math.sin(time * 0.35) * 0.07);
        cursor.ty = height * (0.42 + Math.sin(time * 0.7) * 0.06);
      }

      // Frame-rate independent easing.
      const ease = 1 - Math.pow(0.0015, dt);
      cursor.x += (cursor.tx - cursor.x) * ease;
      cursor.y += (cursor.ty - cursor.y) * ease;

      const radius = Math.min(Math.max(width, height) * 0.36, 460);
      const inner = radius * 0.14;
      const pEase = 1 - Math.pow(0.02, dt);

      for (const p of points) {
        const d = Math.hypot(p.x - cursor.x, p.y - cursor.y);
        let target = 0;
        if (d < radius) {
          // Fade in from the edge, leave a small calm centre, ripple in rings.
          const ring = 0.62 + 0.38 * Math.sin(d * 0.05 - time * 2.2);
          target = smooth(radius, radius * 0.45, d) * smooth(inner * 0.4, inner * 1.6, d) * ring;
        }
        p.k += (target - p.k) * pEase;
      }
    };

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      update(dt);
      draw();
    };

    const start = () => {
      if (running) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(tick);
    };

    const stop = () => {
      running = false;
      cancelAnimationFrame(raf);
    };

    const onPointerMove = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      cursor.inside = x >= 0 && y >= 0 && x <= rect.width && y <= rect.height;
      if (cursor.inside) {
        cursor.tx = x;
        cursor.ty = y;
        lastPointerAt = performance.now();
      }
    };

    const onLeave = () => {
      cursor.inside = false;
    };

    build();

    if (reduceMotion) {
      // One settled, static frame.
      for (let i = 0; i < 90; i++) update(1 / 60);
      draw();
    }

    const resizeObserver = new ResizeObserver(() => {
      build();
      if (!running) draw();
    });
    resizeObserver.observe(host);

    const visibility = new IntersectionObserver(([entry]) => {
      if (reduceMotion) return;
      if (entry.isIntersecting) start();
      else stop();
    });
    visibility.observe(canvas);

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);

    return () => {
      stop();
      resizeObserver.disconnect();
      visibility.disconnect();
      window.removeEventListener("pointermove", onPointerMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, []);

  return <canvas ref={canvasRef} className="hero-field" aria-hidden="true" />;
}
