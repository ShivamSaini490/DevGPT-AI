import { useId } from "react";

/*
  DevGPT mark on a 32×32 grid:
  an outlined "D" with a four-point spark in its counter, plus a small
  twinkle at the top-right. The inner spark is its own path (.logo-spark)
  so it can twinkle/rotate independently (streaming, hover, intro).
*/

// Rounded D with an open counter (even-odd fill).
export const LOGO_D =
  "M8 4h8.5C23.4 4 28 9.2 28 16s-4.6 12-11.5 12H8a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" +
  "M10.6 8.6v14.8h5.8c4.5 0 7.1-3 7.1-7.4s-2.6-7.4-7.1-7.4z";

// Four-point spark centred in the counter (same curve family as the old star).
export const LOGO_SPARK =
  "M16.4 11.6c.4 2.3 2.1 4 4.4 4.4-2.3.4-4 2.1-4.4 4.4-.4-2.3-2.1-4-4.4-4.4 2.3-.4 4-2.1 4.4-4.4z";

// Small twinkle outside the D, top-right.
export const LOGO_TWINKLE =
  "M27.2 1.6c.22 1.3 1.2 2.28 2.5 2.5-1.3.22-2.28 1.2-2.5 2.5-.22-1.3-1.2-2.28-2.5-2.5 1.3-.22 2.28-1.2 2.5-2.5z";

export interface LogoProps {
  size?: number;
  variant?: "gradient" | "current";
  className?: string;
  title?: string;
}

/**
 * variant:
 *  - "gradient" (default): brand gradient
 *  - "current": surrounding text colour
 */
export default function Logo({ size = 20, variant = "gradient", className = "", title }: LogoProps) {
  const id = useId();
  const fill = variant === "gradient" ? `url(#${id})` : "currentColor";
  const small = size < 16; // drop the outer twinkle where it would be noise

  return (
    <svg
      className={`logo ${className}`}
      viewBox="0 0 32 32"
      width={size}
      height={size}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : "true"}
    >
      {variant === "gradient" && (
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--logo-a, #a9c3ff)" />
            <stop offset="0.55" stopColor="var(--logo-b, #5b74ff)" />
            <stop offset="1" stopColor="var(--logo-c, #9b6bff)" />
          </linearGradient>
        </defs>
      )}
      <path fill={fill} fillRule="evenodd" d={LOGO_D} />
      <path className="logo-spark" fill={fill} d={LOGO_SPARK} />
      {!small && <path className="logo-twinkle" fill={fill} d={LOGO_TWINKLE} />}
    </svg>
  );
}
