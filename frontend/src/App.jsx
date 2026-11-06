import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import Splash from "./components/Splash";
import LandingPage from "./pages/LandingPage";
import { useSession } from "./hooks/useSession";
import { useTheme } from "./hooks/useTheme";
import { useRoute } from "./lib/router";

// three.js is the heaviest dependency; load it after the UI paints.
const Background = lazy(() => import("./components/Background"));
// The chat (Markdown + KaTeX) is only downloaded when someone opens it.
const ChatPage = lazy(() => import("./pages/ChatPage"));

const TITLES = {
  landing: "DevGPT — Think It. Say It. DevGPT Reply It.",
  chat: "Chat · DevGPT",
};

export default function App() {
  const { theme, toggle: toggleTheme } = useTheme();
  const { route, navigate } = useRoute();
  useSession();

  const [chatReady, setChatReady] = useState(false);
  const [introDone, setIntroDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const onChatReady = useCallback(() => setChatReady(true), []);

  useEffect(() => {
    document.body.dataset.route = route;
    document.title = TITLES[route];
    if (route !== "chat") setBusy(false);
  }, [route]);

  // The landing page has nothing to load; the chat waits for its history.
  const splashReady = route === "landing" || chatReady;

  return (
    <>
      <Suspense fallback={null}>
        <Background theme={theme} active={busy} />
      </Suspense>

      {!introDone && <Splash ready={splashReady} onDone={() => setIntroDone(true)} />}

      {/* Opacity only: a transform/filter here would break position:fixed children. */}
      <AnimatePresence mode="wait">
        <motion.div
          key={route}
          className={`route route-${route}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35, ease: "easeInOut" }}
        >
          {route === "chat" ? (
            <Suspense fallback={null}>
            <ChatPage
              theme={theme}
              onToggleTheme={toggleTheme}
              introDone={introDone}
              onReady={onChatReady}
              onBusyChange={setBusy}
              onNavigate={navigate}
            />
            </Suspense>
          ) : (
            <LandingPage
              theme={theme}
              onToggleTheme={toggleTheme}
              introDone={introDone}
              onNavigate={navigate}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </>
  );
}
