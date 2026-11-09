import type { AnchorHTMLAttributes, ReactNode } from "react";
import type { Navigate } from "../types";

interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
  onNavigate: Navigate;
  children?: ReactNode;
}

// In-app link: real <a href> (so new-tab / copy-link work), client-side on plain click.
export default function Link({ to, onNavigate, children, ...props }: LinkProps) {
  return (
    <a
      href={to}
      onClick={(event) => {
        if (event.defaultPrevented || event.button !== 0) return;
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        onNavigate(to);
      }}
      {...props}
    >
      {children}
    </a>
  );
}
