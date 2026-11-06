import { useCallback, useEffect, useState } from "react";

// Two routes don't need a router library: "/" (landing) and "/chat".
export function routeFor(pathname) {
  return pathname === "/chat" || pathname.startsWith("/chat/") ? "chat" : "landing";
}

export function useRoute() {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((to) => {
    if (to !== window.location.pathname) {
      window.history.pushState({}, "", to);
      setPath(to);
    }
    window.scrollTo({ top: 0 });
  }, []);

  return { route: routeFor(path), navigate };
}
