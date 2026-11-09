import { useEffect, useRef } from "react";
import * as THREE from "three";
import gsap from "gsap";
import type { Theme } from "../types";

// Soft, slowly drifting gradient glows rendered on a full-screen quad.
// Palettes are tweened with GSAP when the theme changes.

// The shader works directly in sRGB, so keep THREE.Color values as authored.
THREE.ColorManagement.enabled = false;

interface Palette {
  base: string;
  a: string;
  b: string;
  c: string;
  strength: [number, number, number];
  vignette: number;
  grain: number;
}

interface Uniforms {
  [name: string]: THREE.IUniform;
  uRes: THREE.IUniform<THREE.Vector2>;
  uTime: THREE.IUniform<number>;
  uPointer: THREE.IUniform<THREE.Vector2>;
  uBase: THREE.IUniform<THREE.Color>;
  uA: THREE.IUniform<THREE.Color>;
  uB: THREE.IUniform<THREE.Color>;
  uC: THREE.IUniform<THREE.Color>;
  uStrength: THREE.IUniform<THREE.Vector3>;
  uVignette: THREE.IUniform<number>;
  uGrain: THREE.IUniform<number>;
  uActivity: THREE.IUniform<number>;
}

interface RenderState {
  uniforms: Uniforms;
  render: () => void;
  speed: number;
}

const PALETTES: Record<Theme, Palette> = {
  dark: {
    base: "#05070f",
    a: "#1f45c8", // horizon glow under the composer
    b: "#3a2a96", // violet drift, upper left
    c: "#0d5f80", // teal drift, right
    strength: [0.62, 0.38, 0.3],
    vignette: 0.45,
    grain: 0.022,
  },
  light: {
    base: "#f6f7fb",
    a: "#bccdff",
    b: "#e6d9ff",
    c: "#cdeeff",
    strength: [0.75, 0.6, 0.6],
    vignette: 0.0,
    grain: 0.014,
  },
};

const vertexShader = /* glsl */ `
  void main() {
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  precision highp float;

  uniform vec2  uRes;
  uniform float uTime;
  uniform vec2  uPointer;
  uniform vec3  uBase;
  uniform vec3  uA;
  uniform vec3  uB;
  uniform vec3  uC;
  uniform vec3  uStrength;
  uniform float uVignette;
  uniform float uGrain;
  uniform float uActivity;

  float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
  }

  float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 3; i++) {
      v += a * noise(p);
      p *= 2.03;
      a *= 0.5;
    }
    return v;
  }

  float glow(vec2 p, vec2 center, vec2 radius) {
    vec2 d = (p - center) / radius;
    return exp(-dot(d, d));
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / uRes;
    float aspect = uRes.x / uRes.y;
    vec2 p = (uv - 0.5) * vec2(aspect, 1.0);

    float t = uTime * 0.045;

    // Gentle domain warp keeps the glows organic.
    vec2 warp = vec2(fbm(p * 1.4 + t), fbm(p * 1.4 - t + 7.3)) - 0.5;
    vec2 q = p + warp * 0.35;

    vec2 pointer = uPointer * 0.06;

    float a = glow(q, vec2(0.0 + sin(t * 2.0) * 0.08, -0.58 + sin(t * 1.3) * 0.03),
                   vec2(1.05 * max(aspect, 1.0) * 0.6, 0.42 + uActivity * 0.06));
    float b = glow(q, vec2(-0.55 * aspect + sin(t * 1.7) * 0.18, 0.32 + cos(t * 1.1) * 0.1) + pointer,
                   vec2(0.55, 0.45));
    float c = glow(q, vec2(0.6 * aspect + cos(t * 1.4) * 0.16, 0.05 + sin(t * 0.9) * 0.14) - pointer,
                   vec2(0.5, 0.55));

    vec3 col = uBase;
    col = mix(col, uC, clamp(c * uStrength.z, 0.0, 1.0));
    col = mix(col, uB, clamp(b * uStrength.y, 0.0, 1.0));
    col = mix(col, uA, clamp(a * (uStrength.x + uActivity * 0.15), 0.0, 1.0));

    // Vignette (dark theme only — strength is 0 in light).
    float v = smoothstep(1.25, 0.25, length(p * vec2(0.85, 1.0)));
    col *= mix(1.0 - uVignette, 1.0, v);

    // Film grain dithers away gradient banding.
    col += (hash(gl_FragCoord.xy + fract(uTime) * 100.0) - 0.5) * uGrain;

    gl_FragColor = vec4(col, 1.0);
  }
`;

function applyPalette(uniforms: Uniforms, palette: Palette, duration: number): void {
  const targets: [THREE.Color, string][] = [
    [uniforms.uBase.value, palette.base],
    [uniforms.uA.value, palette.a],
    [uniforms.uB.value, palette.b],
    [uniforms.uC.value, palette.c],
  ];

  for (const [color, hex] of targets) {
    const next = new THREE.Color(hex);
    gsap.to(color, { r: next.r, g: next.g, b: next.b, duration, ease: "power2.inOut", overwrite: true });
  }

  const [x, y, z] = palette.strength;
  gsap.to(uniforms.uStrength.value, { x, y, z, duration, ease: "power2.inOut", overwrite: true });
  gsap.to(uniforms.uVignette, { value: palette.vignette, duration, overwrite: true });
  gsap.to(uniforms.uGrain, { value: palette.grain, duration, overwrite: true });
}

interface BackgroundProps {
  theme: Theme;
  active: boolean;
}

export default function Background({ theme, active }: BackgroundProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef<RenderState | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    let renderer: THREE.WebGLRenderer;

    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: "low-power" });
    } catch {
      // No WebGL: the CSS gradient on <body> stays visible instead.
      return undefined;
    }

    const palette = PALETTES[theme] || PALETTES.dark;
    const uniforms: Uniforms = {
      uRes: { value: new THREE.Vector2(1, 1) },
      uTime: { value: 0 },
      uPointer: { value: new THREE.Vector2(0, 0) },
      uBase: { value: new THREE.Color(palette.base) },
      uA: { value: new THREE.Color(palette.a) },
      uB: { value: new THREE.Color(palette.b) },
      uC: { value: new THREE.Color(palette.c) },
      uStrength: { value: new THREE.Vector3(...palette.strength) },
      uVignette: { value: palette.vignette },
      uGrain: { value: palette.grain },
      uActivity: { value: 0 },
    };

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const material = new THREE.ShaderMaterial({ uniforms, vertexShader, fragmentShader, depthTest: false });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    scene.add(mesh);

    renderer.outputColorSpace = THREE.LinearSRGBColorSpace; // no output conversion
    renderer.domElement.className = "bg-canvas";
    renderer.domElement.setAttribute("aria-hidden", "true");
    host.appendChild(renderer.domElement);

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pointerTarget = new THREE.Vector2(0, 0);
    const state: RenderState = { uniforms, render: () => renderer.render(scene, camera), speed: 1 };
    stateRef.current = state;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
      renderer.setPixelRatio(dpr);
      renderer.setSize(window.innerWidth, window.innerHeight, false);
      uniforms.uRes.value.set(window.innerWidth * dpr, window.innerHeight * dpr);
      state.render();
    };

    const onPointer = (event: PointerEvent) => {
      pointerTarget.set(event.clientX / window.innerWidth - 0.5, 0.5 - event.clientY / window.innerHeight);
    };

    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      if (reduceMotion.matches) {
        state.render();
        return;
      }
      uniforms.uTime.value += dt * state.speed;
      uniforms.uPointer.value.lerp(pointerTarget, 0.03);
      state.render();
    };

    const onVisibility = () => {
      cancelAnimationFrame(raf);
      if (document.visibilityState === "visible") {
        last = performance.now();
        raf = requestAnimationFrame(tick);
      }
    };

    resize();
    raf = requestAnimationFrame(tick);
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);

    // Fade the canvas in once the first frame is drawn.
    gsap.fromTo(renderer.domElement, { opacity: 0 }, { opacity: 1, duration: 1.4, ease: "power2.out" });

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointer);
      document.removeEventListener("visibilitychange", onVisibility);
      gsap.killTweensOf([uniforms.uBase.value, uniforms.uA.value, uniforms.uB.value, uniforms.uC.value]);
      mesh.geometry.dispose();
      material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      stateRef.current = null;
    };
    // The renderer is created once; theme/activity changes are tweened below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;
    applyPalette(state.uniforms, PALETTES[theme] || PALETTES.dark, 1.1);
  }, [theme]);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;
    gsap.to(state.uniforms.uActivity, { value: active ? 1 : 0, duration: 1.2, ease: "sine.inOut", overwrite: true });
    gsap.to(state, { speed: active ? 2.4 : 1, duration: 1.2, ease: "sine.inOut", overwrite: true });
  }, [active]);

  return <div ref={hostRef} className="bg-host" />;
}
