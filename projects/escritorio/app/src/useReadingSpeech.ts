import { requireOptionalNativeModule } from "expo";
import { useEffect, useRef, useState } from "react";
import { Platform } from "react-native";

type SpeechModule = {
  addListener: (
    eventName: string,
    listener: (event: any) => void,
  ) => { remove: () => void };
  start: (options: Record<string, unknown>) => void;
  stop: () => void;
  abort: () => void;
  isRecognitionAvailable: () => boolean;
  requestPermissionsAsync: () => Promise<{ granted: boolean }>;
};

const SpeechRecognitionModule =
  requireOptionalNativeModule<SpeechModule>("ExpoSpeechRecognition");

type Options = {
  onFinal: (transcript: string) => void;
  onError: (code: string) => void;
};

function useNativeSpeechEvent(
  eventName: string,
  listener: (event: any) => void,
): void {
  const listenerRef = useRef(listener);
  listenerRef.current = listener;
  useEffect(() => {
    if (!SpeechRecognitionModule) return;
    const subscription = SpeechRecognitionModule.addListener(
      eventName,
      (event) => listenerRef.current(event),
    );
    return () => subscription.remove();
  }, [eventName]);
}

export function useReadingSpeech({
  onFinal,
  onError,
}: Options) {
  const [recognizing, setRecognizing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [interim, setInterim] = useState("");
  const continueRef = useRef(false);
  const startingRef = useRef(false);
  const startTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognizingRef = useRef(false);
  const stopResolvers = useRef<Array<() => void>>([]);
  const callbacks = useRef({ onFinal, onError });
  callbacks.current = { onFinal, onError };

  const continuousSupported =
    Platform.OS !== "android" || Number(Platform.Version) >= 33;

  function startNative(): void {
    if (!SpeechRecognitionModule) throw new Error("speech_module_missing");
    SpeechRecognitionModule.start({
      lang: "pt-BR",
      continuous: continuousSupported,
      interimResults: true,
      maxAlternatives: 1,
      addsPunctuation: true,
      contextualStrings: [
        "quote",
        "citacao",
        "comentario",
        "comentarios Leo",
        "ideia",
        "coach",
        "lista",
      ],
    });
  }

  function clearStartTimeout(): void {
    if (startTimeoutRef.current) clearTimeout(startTimeoutRef.current);
    startTimeoutRef.current = null;
  }

  function armStartTimeout(): void {
    clearStartTimeout();
    startTimeoutRef.current = setTimeout(() => {
      if (!startingRef.current || recognizingRef.current) return;
      continueRef.current = false;
      startingRef.current = false;
      setStarting(false);
      try {
        SpeechRecognitionModule?.abort();
      } catch {
        // O bridge pode nao ter criado uma sessao nativa ainda.
      }
      callbacks.current.onError("start-timeout");
    }, 8000);
  }

  useNativeSpeechEvent("start", () => {
    if (!continueRef.current) {
      try {
        SpeechRecognitionModule?.stop();
      } catch {
        // Fail-closed: nunca reativa a UI depois de timeout/cancelamento.
      }
      return;
    }
    recognizingRef.current = true;
    clearStartTimeout();
    startingRef.current = false;
    setStarting(false);
    setRecognizing(true);
  });

  useNativeSpeechEvent("result", (event) => {
    const transcript = event.results[0]?.transcript?.trim() ?? "";
    if (!transcript) return;
    if (event.isFinal) {
      setInterim("");
      callbacks.current.onFinal(transcript);
    } else {
      setInterim(transcript);
    }
  });

  useNativeSpeechEvent("error", (event) => {
    if (event.error !== "aborted" && event.error !== "no-speech") {
      continueRef.current = false;
      clearStartTimeout();
      startingRef.current = false;
      setStarting(false);
      callbacks.current.onError(event.error);
    }
  });

  useNativeSpeechEvent("end", () => {
    recognizingRef.current = false;
    clearStartTimeout();
    startingRef.current = false;
    setStarting(false);
    setRecognizing(false);
    setInterim("");
    const resolvers = stopResolvers.current;
    stopResolvers.current = [];
    resolvers.forEach((resolve) => resolve());
    if (continueRef.current && !continuousSupported) {
      startingRef.current = true;
      setStarting(true);
      setTimeout(() => {
        if (!continueRef.current) {
          startingRef.current = false;
          setStarting(false);
          return;
        }
        try {
          startNative();
          armStartTimeout();
        } catch {
          continueRef.current = false;
          startingRef.current = false;
          setStarting(false);
          callbacks.current.onError("client");
        }
      }, 250);
    }
  });

  useEffect(
    () => () => {
      continueRef.current = false;
      startingRef.current = false;
      clearStartTimeout();
      try {
        SpeechRecognitionModule?.stop();
      } catch {
        // O recognizer pode ja ter encerrado por uma interrupcao do sistema.
      }
    },
    [],
  );

  async function start(): Promise<boolean> {
    if (recognizingRef.current || startingRef.current) return false;
    startingRef.current = true;
    setStarting(true);
    try {
      if (
        !SpeechRecognitionModule ||
        !SpeechRecognitionModule.isRecognitionAvailable()
      ) {
        callbacks.current.onError("service-not-allowed");
        startingRef.current = false;
        setStarting(false);
        return false;
      }
      const permission =
        await SpeechRecognitionModule.requestPermissionsAsync();
      if (!permission.granted) {
        callbacks.current.onError("not-allowed");
        startingRef.current = false;
        setStarting(false);
        return false;
      }
      continueRef.current = true;
      startNative();
      armStartTimeout();
      return true;
    } catch {
      continueRef.current = false;
      startingRef.current = false;
      setStarting(false);
      callbacks.current.onError("client");
      return false;
    }
  }

  function stop(): Promise<void> {
    continueRef.current = false;
    if (!recognizingRef.current) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const done = () => {
        clearTimeout(timeout);
        resolve();
      };
      const timeout = setTimeout(() => {
        stopResolvers.current = stopResolvers.current.filter(
          (candidate) => candidate !== done,
        );
        callbacks.current.onError("stop-timeout");
        reject(new Error("speech_stop_timeout"));
      }, 8000);
      stopResolvers.current.push(done);
      if (!SpeechRecognitionModule) {
        reject(new Error("speech_module_missing"));
        return;
      }
      SpeechRecognitionModule.stop();
    });
  }

  return {
    recognizing,
    starting,
    interim,
    continuousSupported,
    nativeAvailable: SpeechRecognitionModule !== null,
    start,
    stop,
  };
}
