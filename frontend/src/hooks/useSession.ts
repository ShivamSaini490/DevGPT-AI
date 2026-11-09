import { useEffect } from "react";
import { sendCloseBeacon, sendHeartbeat } from "../lib/api";

const HEARTBEAT_MS = 60_000;

// Keeps this browser's backend session alive while the tab is open.
// The backend clears a client's chats after it stops hearing from it.
export function useSession(): void {
  useEffect(() => {
    sendHeartbeat();
    const timer = setInterval(sendHeartbeat, HEARTBEAT_MS);

    const onVisible = () => {
      if (document.visibilityState === "visible") sendHeartbeat();
    };
    const onPageHide = () => sendCloseBeacon();

    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onVisible);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onVisible);
    };
  }, []);
}
