import { useCallback, useEffect, useRef, useState } from "react";

// Minimal typings for the Web Speech API (not in every TS DOM lib).
interface SpeechAlternative {
  transcript: string;
}

interface SpeechResult {
  readonly isFinal: boolean;
  readonly [index: number]: SpeechAlternative;
}

interface SpeechResultEvent {
  resultIndex: number;
  results: ArrayLike<SpeechResult>;
}

interface SpeechErrorEvent {
  error: string;
}

interface SpeechRecognizer {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

type SpeechRecognizerConstructor = new () => SpeechRecognizer;

const speechWindow =
  typeof window !== "undefined"
    ? (window as unknown as {
        SpeechRecognition?: SpeechRecognizerConstructor;
        webkitSpeechRecognition?: SpeechRecognizerConstructor;
      })
    : undefined;

const SpeechRecognition: SpeechRecognizerConstructor | undefined =
  speechWindow?.SpeechRecognition || speechWindow?.webkitSpeechRecognition;

export interface Dictation {
  listening: boolean;
  interim: string;
  error: string | null;
  toggle: () => void;
  stop: () => void;
  supported: boolean;
}

/**
 * Browser speech-to-text. `onFinal` receives each finalized phrase,
 * `interim` holds the in-progress transcript.
 */
export function useDictation(onFinal: (text: string) => void): Dictation {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognizer | null>(null);
  const wantRef = useRef(false);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const stop = useCallback(() => {
    wantRef.current = false;
    setListening(false);
    setInterim("");
    try {
      recognitionRef.current?.stop();
    } catch {
      /* already stopped */
    }
  }, []);

  const start = useCallback(() => {
    if (!SpeechRecognition) {
      setError("Speech recognition isn't supported in this browser. Try Chrome or Edge.");
      return;
    }

    if (!recognitionRef.current) {
      const recognition = new SpeechRecognition();
      recognition.lang = navigator.language || "en-US";
      recognition.continuous = true;
      recognition.interimResults = true;

      recognition.onresult = (event) => {
        let finalText = "";
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += transcript + " ";
          else interimText += transcript;
        }
        if (finalText.trim()) onFinalRef.current?.(finalText.trim());
        setInterim(interimText);
      };

      recognition.onerror = (event) => {
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          setError("Microphone access was denied.");
        }
        if (event.error !== "no-speech") stop();
      };

      // Chrome ends sessions after silence; restart while the user wants it on.
      recognition.onend = () => {
        if (wantRef.current) {
          try {
            recognition.start();
          } catch {
            stop();
          }
        }
      };

      recognitionRef.current = recognition;
    }

    setError(null);
    wantRef.current = true;
    try {
      recognitionRef.current.start();
      setListening(true);
    } catch {
      /* start() throws if already started */
    }
  }, [stop]);

  const toggle = useCallback(() => (wantRef.current ? stop() : start()), [start, stop]);

  useEffect(() => () => stop(), [stop]);

  return { listening, interim, error, toggle, stop, supported: Boolean(SpeechRecognition) };
}
