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

type PendingStop = {
  resolve: () => void;
  reject: (error: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
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
  const startRequestRef = useRef(0);
  const nativeStartPendingRef = useRef(false);
  const drainingRef = useRef(false);
  const pendingStopsRef = useRef<PendingStop[]>([]);
  const callbacks = useRef({ onFinal, onError });
  callbacks.current = { onFinal, onError };

  const continuousSupported =
    Platform.OS !== "android" || Number(Platform.Version) >= 33;

  function startNative(): void {
    if (!SpeechRecognitionModule) throw new Error("speech_module_missing");
    nativeStartPendingRef.current = true;
    SpeechRecognitionModule.start({
      lang: "pt-BR",
      continuous: continuousSupported,
      interimResults: true,
      maxAlternatives: 1,
      addsPunctuation: true,
      contextualStrings: [
        "citação",
        "citacao",
        "quote",
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
      drainingRef.current = true;
      setStarting(false);
      try {
        SpeechRecognitionModule?.abort();
      } catch {
        // O bridge pode nao ter criado uma sessao nativa ainda.
      }
      callbacks.current.onError("start-timeout");
    }, 8000);
  }

  function settlePendingStops(error?: Error): void {
    const pending = pendingStopsRef.current;
    pendingStopsRef.current = [];
    pending.forEach((request) => {
      clearTimeout(request.timeout);
      if (error) request.reject(error);
      else request.resolve();
    });
  }

  function abortRecognition(code: string, error: Error): void {
    continueRef.current = false;
    startingRef.current = false;
    recognizingRef.current = false;
    drainingRef.current = true;
    clearStartTimeout();
    try {
      SpeechRecognitionModule?.abort();
    } catch {
      // O servico pode ter encerrado antes de receber o abort.
    }
    setStarting(false);
    setRecognizing(false);
    setInterim("");
    callbacks.current.onError(code);
    settlePendingStops(error);
  }

  useNativeSpeechEvent("start", () => {
    if (!continueRef.current) {
      drainingRef.current = true;
      try {
        SpeechRecognitionModule?.abort();
      } catch {
        // Fail-closed: nunca reativa a UI depois de timeout/cancelamento.
      }
      return;
    }
    nativeStartPendingRef.current = false;
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
    nativeStartPendingRef.current = false;
    drainingRef.current = false;
    recognizingRef.current = false;
    clearStartTimeout();
    startingRef.current = false;
    setStarting(false);
    setRecognizing(false);
    setInterim("");
    settlePendingStops();
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
          nativeStartPendingRef.current = false;
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
      startRequestRef.current += 1;
      continueRef.current = false;
      startingRef.current = false;
      recognizingRef.current = false;
      drainingRef.current = true;
      clearStartTimeout();
      try {
        SpeechRecognitionModule?.abort();
      } catch {
        // O recognizer pode ja ter encerrado por uma interrupcao do sistema.
      }
      settlePendingStops(new Error("speech_unmounted"));
    },
    [],
  );

  async function start(): Promise<boolean> {
    if (recognizingRef.current || startingRef.current) return false;
    if (drainingRef.current) {
      callbacks.current.onError("recognizer-draining");
      return false;
    }
    const requestId = startRequestRef.current + 1;
    startRequestRef.current = requestId;
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
      if (startRequestRef.current !== requestId || !startingRef.current) {
        return false;
      }
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
      nativeStartPendingRef.current = false;
      continueRef.current = false;
      startingRef.current = false;
      setStarting(false);
      callbacks.current.onError("client");
      return false;
    }
  }

  function stop(): Promise<void> {
    startRequestRef.current += 1;
    continueRef.current = false;
    if (!recognizingRef.current) {
      if (startingRef.current) {
        const nativeStartPending = nativeStartPendingRef.current;
        startingRef.current = false;
        setStarting(false);
        clearStartTimeout();
        if (nativeStartPending) {
          drainingRef.current = true;
          try {
            SpeechRecognitionModule?.abort();
          } catch {
            // O evento terminal ainda precisa drenar antes de um novo inicio.
          }
        }
      }
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        abortRecognition(
          "stop-timeout",
          new Error("speech_stop_timeout"),
        );
      }, 8000);
      pendingStopsRef.current.push({ resolve, reject, timeout });
      if (!SpeechRecognitionModule) {
        abortRecognition(
          "speech-module-missing",
          new Error("speech_module_missing"),
        );
        return;
      }
      try {
        SpeechRecognitionModule.stop();
      } catch {
        abortRecognition("stop-failed", new Error("speech_stop_failed"));
      }
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
