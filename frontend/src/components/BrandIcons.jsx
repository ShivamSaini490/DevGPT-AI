// Brand marks drawn inline (lucide-react v1 no longer ships brand icons).

export function GithubIcon({ size = 18, ...props }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.42-2.7 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

export function FigmaIcon({ size = 18, ...props }) {
  // Five-shape mark in the brand's colours.
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" {...props}>
      <path fill="#f24e1e" d="M8.5 1h3.5v7H8.5a3.5 3.5 0 1 1 0-7Z" />
      <path fill="#ff7262" d="M12 1h3.5a3.5 3.5 0 1 1 0 7H12V1Z" />
      <path fill="#a259ff" d="M8.5 8H12v7H8.5a3.5 3.5 0 1 1 0-7Z" />
      <circle fill="#1abcfe" cx="15.5" cy="11.5" r="3.5" />
      <path fill="#0acf83" d="M8.5 15H12v3.5A3.5 3.5 0 1 1 8.5 15Z" />
    </svg>
  );
}
