import { useEffect, useRef } from "react";

// A slowly turning ring of dots, tilted toward the pointer. Canvas 2D keeps it
// cheap; it only animates while on screen.
const COUNT = 1100;

interface RingPoint {
  t: number;
  r: number;
  y: number;
  s: number;
}

function makePoints(): RingPoint[] {
  return Array.from({ length: COUNT }, () => {
    const spread = Math.random() * Math.random();
    return {
      t: Math.random() * Math.PI * 2,
      r: 1 + (Math.random() - 0.5) * 0.42 * spread,
      y: (Math.random() - 0.5) * 0.3 * spread,
      s: Math.random(),
    };
  });
}

export default function ParticleRing({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return undefined;
    const points = makePoints();
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let raf = 0;
    let visible = false;
    let last = performance.now();
    let rotation = 0;
    const tilt = { x: 1.05, y: 0, tx: 1.05, ty: 0 };

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    };

    const draw = () => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      const radius = Math.min(width, height * 1.6) * 0.32;
      const cx = width * 0.66;
      const cy = height * 0.5;
      const cosX = Math.cos(tilt.x);
      const sinX = Math.sin(tilt.x);
      const cosY = Math.cos(tilt.y);
      const sinY = Math.sin(tilt.y);

      for (const p of points) {
        const a = p.t + rotation;
        let x = Math.cos(a) * p.r;
        let z = Math.sin(a) * p.r;
        let y = p.y;

        // Tilt around X, then a little around Y.
        const y1 = y * cosX - z * sinX;
        const z1 = y * sinX + z * cosX;
        const x2 = x * cosY + z1 * sinY;
        const z2 = -x * sinY + z1 * cosY;

        const scale = 2.6 / (2.6 + z2);
        const sx = cx + x2 * radius * scale;
        const sy = cy + y1 * radius * scale;
        const depth = (1 - z2) / 2; // 0 (back) … 1 (front)
        const size = (0.7 + p.s * 1.5) * scale;

        ctx.globalAlpha = 0.18 + depth * 0.75;
        ctx.fillStyle = p.s > 0.72 ? "#ffffff" : p.s > 0.35 ? "#8fa8ff" : "#4f6bff";
        ctx.fillRect(sx, sy, size, size);
      }
      ctx.globalAlpha = 1;
    };

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      rotation += dt * 0.16;
      tilt.x += (tilt.tx - tilt.x) * 0.04;
      tilt.y += (tilt.ty - tilt.y) * 0.04;
      draw();
    };

    const start = () => {
      if (reduceMotion || raf) return;
      last = performance.now();
      raf = requestAnimationFrame(tick);
    };

    const stop = () => {
      cancelAnimationFrame(raf);
      raf = 0;
    };

    const onPointer = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const nx = (event.clientX - rect.left) / rect.width - 0.5;
      const ny = (event.clientY - rect.top) / rect.height - 0.5;
      tilt.tx = 1.05 + ny * 0.5;
      tilt.ty = nx * 0.6;
    };

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible) start();
      else stop();
    });

    resize();
    draw();
    observer.observe(canvas);
    window.addEventListener("resize", resize);
    canvas.parentElement?.addEventListener("pointermove", onPointer);

    return () => {
      stop();
      observer.disconnect();
      window.removeEventListener("resize", resize);
      canvas.parentElement?.removeEventListener("pointermove", onPointer);
    };
  }, []);

  return <canvas ref={canvasRef} className={`particle-ring ${className}`} aria-hidden="true" />;
}
