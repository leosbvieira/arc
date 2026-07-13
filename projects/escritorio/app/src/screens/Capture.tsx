import { Feather } from "@expo/vector-icons";
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  AppState,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { capture } from "../api";
import {
  createCaptureClientKey,
  enqueue,
  flush,
  pendingCount,
} from "../captureQueue";
import {
  clearReadingDraft,
  loadReadingDraft,
  ReadingDraft,
  ReadingDraftItem,
  saveReadingDraft,
} from "../readingDraft";
import {
  appendReadingBuffer,
  compileReadingSession,
  createReadingSession,
  discardReadingSession,
  listPendingReadingSessions,
  ReadingHook,
  ReadingSession,
} from "../readingApi";
import { colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, Field } from "../ui";
import { useReadingSpeech } from "../useReadingSpeech";

type Mode = "captura" | "leitura";
type Item = ReadingDraftItem;

const KIND: Record<string, { color: string; icon: any }> = {
  "citação": { color: colors.primary, icon: "book-open" },
  "comentário": { color: colors.textMuted, icon: "message-square" },
  ideia: { color: "#A88CBE", icon: "zap" },
  coach: { color: "#6FB58C", icon: "user" },
};

function parse(raw: string): { kind?: string; book?: string; text: string } {
  const t = raw.trim();
  const l = t.toLowerCase();
  const after = () =>
    t.includes(":") ? t.slice(t.indexOf(":") + 1).trim() : t;
  if (l.startsWith("livro")) return { book: after(), text: "" };
  // Hooks falados da spec B7: "quote" = citação verbatim; "comentário" = pensamento.
  if (l.startsWith("quote") || l.startsWith("cita")) {
    return { kind: "citação", text: after() };
  }
  if (l.startsWith("coment")) {
    return { kind: "comentário", text: after() };
  }
  if (l.startsWith("ideia")) return { kind: "ideia", text: after() };
  if (l.startsWith("coach")) return { kind: "coach", text: after() };
  if (l.startsWith("lista")) return { kind: "lista", text: after() };
  return { kind: "comentário", text: t };
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
}

function createSessionKey(ts: number): string {
  return `session:${createCaptureClientKey(ts)}`;
}

function kindToHook(kind: string): ReadingHook {
  if (kind === "citação") return "quote";
  if (kind === "comentário") return "comentario";
  if (kind === "ideia" || kind === "coach" || kind === "lista") {
    return kind;
  }
  return "texto";
}

function hookToKind(hook: ReadingHook): string {
  if (hook === "quote") return "citação";
  if (hook === "comentario" || hook === "texto") return "comentário";
  return hook;
}

function draftFromRemote(session: ReadingSession): ReadingDraft {
  return {
    sessionKey: session.client_key,
    remoteId: session.id,
    book: session.livro ?? "",
    pageStart:
      session.pagina_inicial === null
        ? ""
        : String(session.pagina_inicial),
    pageEnd:
      session.pagina_final === null ? "" : String(session.pagina_final),
    startedAt: Math.round(session.inicio * 1000),
    updatedAt: Date.now(),
    items: (session.buffer ?? []).map((chunk) => ({
      id: `${session.client_key}:${chunk.seq}`,
      kind: hookToKind(chunk.hook),
      text: chunk.texto,
      seq: chunk.seq,
    })),
    syncedSeq: Math.max(0, ...(session.buffer ?? []).map((chunk) => chunk.seq)),
    status: "pending",
  };
}

export default function Capture() {
  const [mode, setMode] = useState<Mode>("captura");

  // captura livre
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [pending, setPending] = useState(0);
  const [status, setStatus] = useState("");

  // sessão de leitura
  const [book, setBook] = useState("");
  const [pageStart, setPageStart] = useState("");
  const [pageEnd, setPageEnd] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [entry, setEntry] = useState("");
  const [compiling, setCompiling] = useState(false);
  const [sessionStart, setSessionStart] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [speechError, setSpeechError] = useState("");
  const [serverPending, setServerPending] = useState<ReadingSession[]>([]);
  const draftRef = useRef<ReadingDraft | null>(null);
  const syncChain = useRef<Promise<void>>(Promise.resolve());

  const speech = useReadingSpeech({
    onFinal: appendTranscript,
    onError: (code) => {
      setSpeechError(`transcrição indisponível (${code}) — entrada manual continua`);
    },
  });

  // O flush global fica em App; esta tela só atualiza o badge local no foco.
  useEffect(() => {
    let alive = true;
    const refreshPending = async () => {
      const count = await pendingCount();
      if (alive) setPending(count);
    };
    refreshPending();
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") refreshPending();
    });
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);

  useEffect(() => {
    let alive = true;

    const restore = async () => {
      let draft = await loadReadingDraft();
      try {
        const pendingRemote = await listPendingReadingSessions();
        if (!alive) return;
        setServerPending(pendingRemote.sessions);
        if (!draft && pendingRemote.sessions.length === 1) {
          draft = draftFromRemote(pendingRemote.sessions[0]);
        } else if (!draft && pendingRemote.sessions.length > 1) {
          setMode("leitura");
          setStatus(
            `${pendingRemote.sessions.length} sessões pendentes — escolha uma para retomar`,
          );
        }
      } catch {
        // Sem rede: o draft local continua sendo a unica fonte de recuperacao.
      }
      if (!alive || !draft) return;

      draftRef.current = draft;
      setBook(draft.book);
      setPageStart(draft.pageStart);
      setPageEnd(draft.pageEnd);
      setItems(draft.items);
      setSessionStart(draft.startedAt);
      setMode("leitura");
      setStatus("sessão de leitura recuperada — revise e retome ou compile");
      await saveReadingDraft(draft);
      queueDraftSync(draft);
    };

    restore();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const draft = draftRef.current;
    if (!draft) return;
    const timer = setTimeout(() => {
      const current = draftRef.current;
      if (!current) return;
      const next = {
        ...current,
        book,
        pageStart,
        pageEnd,
        updatedAt: Date.now(),
      };
      draftRef.current = next;
      saveReadingDraft(next).catch(() => {
        setStatus("não consegui atualizar o buffer local");
      });
    }, 250);
    return () => clearTimeout(timer);
  }, [book, pageStart, pageEnd]);

  useEffect(() => {
    if (sessionStart === null) {
      setElapsedSeconds(0);
      return;
    }

    const update = () => {
      setElapsedSeconds(
        Math.floor((Date.now() - sessionStart) / 1000),
      );
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [sessionStart]);

  async function onSend() {
    const t = text.trim();
    if (!t) return;

    const ts = Date.now();
    const clientKey = createCaptureClientKey(ts);

    setBusy(true);
    setStatus("");
    try {
      const restantes = await flush();
      if (restantes > 0) {
        await enqueue({
          kind: "capture",
          payload: { text: t, client_key: clientKey, sensivel: sensitive },
          ts,
        });
        setText("");
        setSensitive(false);
        setPending(await pendingCount());
        setStatus(
          "sem conexão — guardado no aparelho, reenvio automático",
        );
        return;
      }

      const r = await capture(t, undefined, clientKey, sensitive);
      setReply(r);
      setText("");
      setSensitive(false);
      setPending(await pendingCount());
    } catch {
      // A mesma client_key usada no primeiro POST acompanha o retry. Se o BFF
      // recebeu a captura e só a resposta se perdeu, ele devolve o id existente.
      await enqueue({
        kind: "capture",
        payload: { text: t, client_key: clientKey, sensivel: sensitive },
        ts,
      });
      setText("");
      setSensitive(false);
      setPending(await pendingCount());
      setStatus(
        "sem conexão — guardado no aparelho, reenvio automático",
      );
    } finally {
      setBusy(false);
    }
  }

  function queueDraftSync(
    draft: ReadingDraft,
    localSave: Promise<void> = Promise.resolve(),
  ): void {
    syncChain.current = syncChain.current
      .then(async () => {
        await localSave;
        await syncDraft(draft);
      })
      .catch(() => {
        setStatus("sessão salva no aparelho — autosave no servidor pendente");
      });
  }

  async function restoreRemote(session: ReadingSession): Promise<void> {
    if (draftRef.current) return;
    const draft = draftFromRemote(session);
    draftRef.current = draft;
    setBook(draft.book);
    setPageStart(draft.pageStart);
    setPageEnd(draft.pageEnd);
    setItems(draft.items);
    setSessionStart(draft.startedAt);
    setStatus("sessão pendente aberta — retome ou compile");
    await saveReadingDraft(draft);
  }

  async function syncDraft(snapshot: ReadingDraft): Promise<number> {
    let remoteId = snapshot.remoteId;
    if (remoteId === null) {
      const created = await createReadingSession({
        client_key: snapshot.sessionKey,
        livro: snapshot.book,
        pagina_inicial: numericPage(snapshot.pageStart),
        inicio: snapshot.startedAt / 1000,
      });
      remoteId = created.session.id;
      const current = draftRef.current;
      if (current?.sessionKey === snapshot.sessionKey) {
        const withRemote = { ...current, remoteId };
        draftRef.current = withRemote;
        await saveReadingDraft(withRemote);
      }
    }

    const currentConfirmed =
      draftRef.current?.sessionKey === snapshot.sessionKey
        ? draftRef.current.syncedSeq
        : snapshot.syncedSeq;
    let confirmedSeq = currentConfirmed;
    for (const item of snapshot.items) {
      if (item.seq <= currentConfirmed) continue;
      await appendReadingBuffer(remoteId, {
        seq: item.seq,
        hook: kindToHook(item.kind),
        texto: item.text,
        ts: snapshot.updatedAt / 1000,
      });
      confirmedSeq = item.seq;
    }
    const current = draftRef.current;
    if (
      current?.sessionKey === snapshot.sessionKey &&
      confirmedSeq > current.syncedSeq
    ) {
      const synced = { ...current, remoteId, syncedSeq: confirmedSeq };
      draftRef.current = synced;
      await saveReadingDraft(synced);
    }
    return remoteId;
  }

  function appendTranscript(raw: string): void {
    const parsed = parse(raw);
    if (parsed.book) {
      if (draftRef.current) {
        setSpeechError("o livro não muda depois que a sessão começou");
        return;
      }
      setBook(parsed.book);
      return;
    }
    if (!parsed.text) return;

    const current = draftRef.current;
    if (!current) {
      setEntry(raw);
      setSpeechError("inicie a sessão antes de registrar uma fala");
      return;
    }
    const seq = (current.items.at(-1)?.seq ?? 0) + 1;
    const item: Item = {
      id: `${current.sessionKey}:${seq}`,
      kind: parsed.kind ?? "comentário",
      text: parsed.text,
      seq,
    };
    const next: ReadingDraft = {
      ...current,
      book,
      pageStart,
      pageEnd,
      items: [...current.items, item],
      updatedAt: Date.now(),
      status: "active",
    };
    draftRef.current = next;
    setItems(next.items);
    const localSave = saveReadingDraft(next);
    queueDraftSync(next, localSave);
    localSave.catch(() =>
      setStatus("não consegui gravar o buffer local"),
    );
  }

  function onAdd() {
    const raw = entry.trim();
    if (!raw) return;
    appendTranscript(raw);
    setEntry("");
  }

  function numericPage(value: string): number | null {
    if (!value.trim()) return null;
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
  }

  async function startSession(): Promise<void> {
    if (speech.starting) return;
    setSpeechError("");
    let draft = draftRef.current;
    if (!draft) {
      if (!book.trim()) {
        setSpeechError("informe o livro antes de iniciar a sessão");
        return;
      }
      const now = Date.now();
      draft = {
        sessionKey: createSessionKey(now),
        remoteId: null,
        book,
        pageStart,
        pageEnd,
        startedAt: now,
        updatedAt: now,
        items: [],
        syncedSeq: 0,
        status: "active",
      };
      draftRef.current = draft;
      setSessionStart(now);
      await saveReadingDraft(draft);
      queueDraftSync(draft);
    }
    const started = await speech.start();
    if (started) setStatus("ouvindo — diga ‘quote’, ‘comentário’, ‘ideia’ ou ‘lista’");
  }

  async function stopSpeech(): Promise<void> {
    try {
      await speech.stop();
      setStatus("áudio pausado — o buffer continua salvo");
    } catch {
      setStatus("o microfone não confirmou a pausa — buffer preservado");
    }
  }

  function resetSessionUi(): void {
    draftRef.current = null;
    setSessionStart(null);
    setItems([]);
    setBook("");
    setPageStart("");
    setPageEnd("");
    setEntry("");
    setSpeechError("");
  }

  async function compileNow(): Promise<void> {
    const draft = draftRef.current;
    if (!draft || compiling || draft.items.length === 0) return;
    setCompiling(true);
    setStatus("compilando — o buffer só será limpo após o vault confirmar");
    try {
      const pendingDraft = {
        ...draft,
        book,
        pageStart,
        pageEnd,
        status: "pending" as const,
        updatedAt: Date.now(),
      };
      draftRef.current = pendingDraft;
      await saveReadingDraft(pendingDraft);
      const remoteId = await syncDraft(pendingDraft);
      const result = await compileReadingSession(remoteId, {
        pagina_final: numericPage(pageEnd),
        fim: Date.now() / 1000,
      });
      await clearReadingDraft();
      setServerPending((previous) =>
        previous.filter((session) => session.id !== remoteId),
      );
      resetSessionUi();
      Alert.alert(
        "Sessão compilada",
        result.anki_cards.length > 0
          ? `${result.anki_cards.length} candidato(s) Anki aguardam revisão.`
          : "Nota gravada. Nenhum candidato Anki foi sugerido.",
      );
    } catch {
      const current = draftRef.current;
      if (current) {
        const pendingDraft = {
          ...current,
          status: "pending" as const,
          updatedAt: Date.now(),
        };
        draftRef.current = pendingDraft;
        await saveReadingDraft(pendingDraft);
      }
      setStatus("compilação falhou — sessão pendente, nada foi apagado");
    } finally {
      setCompiling(false);
    }
  }

  async function compilar(): Promise<void> {
    if (speech.starting) {
      setStatus("aguarde o microfone iniciar antes de compilar");
      return;
    }
    if (speech.recognizing) {
      setStatus("finalizando a última fala…");
      try {
        await speech.stop();
      } catch {
        setStatus("não confirmei o fim do áudio — buffer preservado");
        return;
      }
      await syncChain.current;
    }
    await compileNow();
  }

  function descartar(): void {
    const draft = draftRef.current;
    if (!draft) return;
    Alert.alert(
      "Descartar sessão?",
      "O buffer local e a sessão pendente serão removidos.",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Descartar",
          style: "destructive",
          onPress: async () => {
            try {
              if (speech.starting) {
                setStatus("aguarde o microfone iniciar antes de descartar");
                return;
              }
              if (speech.recognizing) await speech.stop();
              await syncChain.current;
              const current = draftRef.current;
              if (!current) return;
              let remoteId = current.remoteId;
              if (remoteId === null) {
                const recovered = await createReadingSession({
                  client_key: current.sessionKey,
                  livro: current.book,
                  pagina_inicial: numericPage(current.pageStart),
                  inicio: current.startedAt / 1000,
                });
                remoteId = recovered.session.id;
              }
              if (remoteId !== null) {
                await discardReadingSession(remoteId);
                setServerPending((previous) =>
                  previous.filter((session) => session.id !== remoteId),
                );
              }
              await clearReadingDraft();
              resetSessionUi();
              setStatus("sessão descartada");
            } catch {
              setStatus("não confirmei o descarte no servidor — sessão preservada");
            }
          },
        },
      ],
    );
  }

  return (
    <View style={{ flex: 1, paddingTop: spacing.sm }}>
      <View style={styles.modebar}>
        {(["captura", "leitura"] as Mode[]).map((m) => (
          <Pressable
            key={m}
            onPress={() => setMode(m)}
            style={[styles.mode, mode === m && styles.modeOn]}
          >
            <Text
              style={[
                styles.modeTxt,
                mode === m && styles.modeTxtOn,
              ]}
            >
              {m === "captura" ? "Captura" : "Leitura"}
            </Text>
          </Pressable>
        ))}
      </View>

      {mode === "captura" ? (
        <View
          style={{
            gap: spacing.md,
            paddingTop: spacing.md,
          }}
        >
          <Text style={styles.hint}>
            Fala ou digita — vira tarefa ou nota.
          </Text>
          <Field
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="ex.: cobrar Ana o relatório sexta"
            multiline
          />
          <Pressable
            onPress={() => setSensitive((value) => !value)}
            style={[styles.sensitiveToggle, sensitive && styles.sensitiveToggleOn]}
          >
            <Feather
              name={sensitive ? "shield" : "shield-off"}
              size={14}
              color={sensitive ? colors.primary : colors.textMuted}
            />
            <Text
              style={[
                styles.sensitiveText,
                sensitive && { color: colors.primary },
              ]}
            >
              conteúdo sensível · preview sempre neutro
            </Text>
          </Pressable>
          <AppButton
            title="Enviar"
            onPress={onSend}
            loading={busy}
          />
          {pending > 0 ? (
            <View style={styles.queueRow}>
              <Feather
                name="clock"
                size={12}
                color={colors.textMuted}
              />
              <Text style={styles.queueText}>
                {pending} na fila local
              </Text>
            </View>
          ) : null}
          {status ? (
            <Text style={styles.status}>{status}</Text>
          ) : null}
          {reply ? (
            <Card style={styles.reply}>
              <Feather
                name="check-circle"
                size={18}
                color={colors.success}
              />
              <Text style={styles.replyText}>{reply}</Text>
            </Card>
          ) : null}
        </View>
      ) : (
        <View style={{ flex: 1, paddingTop: spacing.md }}>
          {sessionStart === null && serverPending.length > 0 ? (
            <View style={styles.pendingSessions}>
              <Text style={styles.pendingTitle}>sessões pendentes</Text>
              {serverPending.map((session) => (
                <Pressable
                  key={session.id}
                  style={styles.pendingSession}
                  onPress={() => restoreRemote(session)}
                >
                  <Feather name="rotate-ccw" size={14} color={colors.primary} />
                  <Text style={styles.pendingSessionText} numberOfLines={1}>
                    {session.livro || "Leitura sem título"} · {session.buffer?.length ?? 0} itens
                  </Text>
                </Pressable>
              ))}
            </View>
          ) : null}
          <View style={styles.sessionFields}>
            <Field
              value={book}
              onChangeText={setBook}
              placeholder="Livro"
              editable={sessionStart === null}
            />
            <View style={styles.pagesRow}>
              <Field
                style={{ flex: 1 }}
                value={pageStart}
                onChangeText={setPageStart}
                placeholder="Página inicial"
                keyboardType="number-pad"
                editable={sessionStart === null}
              />
              <Field
                style={{ flex: 1 }}
                value={pageEnd}
                onChangeText={setPageEnd}
                placeholder="Página final (opcional)"
                keyboardType="number-pad"
              />
            </View>
            <AppButton
              title={
                speech.starting
                  ? "preparando microfone…"
                  : speech.recognizing
                  ? "■ pausar áudio"
                  : sessionStart === null
                    ? "▶ iniciar sessão com áudio"
                    : "▶ retomar áudio"
              }
              variant="ghost"
              onPress={speech.recognizing ? stopSpeech : startSession}
              disabled={speech.starting}
            />
            {sessionStart !== null ? (
              <View style={styles.timerRow}>
                <Feather
                  name="clock"
                  size={15}
                  color={colors.primary}
                />
                <Text style={styles.timerText}>
                  {formatElapsed(elapsedSeconds)}
                </Text>
                <View
                  style={[
                    styles.recordingDot,
                    speech.recognizing && styles.recordingDotOn,
                  ]}
                />
                <Text style={styles.recordingText}>
                  {speech.recognizing ? "ouvindo" : "buffer salvo"}
                </Text>
              </View>
            ) : null}
            {speech.interim ? (
              <Text style={styles.interim}>{speech.interim}</Text>
            ) : null}
            {speechError ? (
              <Text style={styles.status}>{speechError}</Text>
            ) : null}
            {!speech.continuousSupported ? (
              <Text style={styles.status}>
                neste Android a transcrição reinicia a cada fala; o buffer continua persistente
              </Text>
            ) : null}
          </View>

          <View style={styles.bookHead}>
            <Feather
              name="book"
              size={16}
              color={colors.primary}
            />
            <Text
              style={styles.bookTitle}
              numberOfLines={1}
            >
              {book.trim() || "Sessão de leitura"}
            </Text>
            <Text style={styles.bookCount}>
              {items.length} itens
            </Text>
          </View>

          <ScrollView
            style={{
              flex: 1,
              marginTop: spacing.sm,
            }}
            showsVerticalScrollIndicator={false}
          >
            {items.map((it) => {
              const k = KIND[it.kind] ?? KIND["comentário"];
              return (
                <View
                  key={it.id}
                  style={[
                    styles.item,
                    { borderLeftColor: k.color },
                  ]}
                >
                  <View style={styles.itemHead}>
                    <Feather
                      name={k.icon}
                      size={12}
                      color={k.color}
                    />
                    <Text
                      style={[
                        styles.itemKind,
                        { color: k.color },
                      ]}
                    >
                      {it.kind}
                    </Text>
                  </View>
                  <Text style={styles.itemText}>
                    {it.text}
                  </Text>
                </View>
              );
            })}
          </ScrollView>

          <View style={styles.addRow}>
            <Field
              style={{ flex: 1 }}
              value={entry}
              onChangeText={setEntry}
              placeholder='ex.: "citação: ..." ou "ideia: ..."'
            />
            <Pressable
              onPress={onAdd}
              style={styles.addBtn}
            >
              <Feather
                name="plus"
                size={22}
                color={colors.primaryText}
              />
            </Pressable>
          </View>
          <AppButton
            title="Compilar sessão"
            variant="ghost"
            onPress={compilar}
            loading={compiling}
            disabled={
              speech.starting || sessionStart === null || items.length === 0
            }
          />
          {sessionStart !== null ? (
            <View style={styles.compileMeta}>
              <Text style={styles.compileHint}>
                A IA sugere candidatos Anki depois da compilação; você aprova na Revisão.
              </Text>
              <Pressable onPress={descartar} hitSlop={8}>
                <Text style={styles.discardText}>descartar sessão</Text>
              </Pressable>
            </View>
          ) : null}
          {pending > 0 ? (
            <View style={styles.queueRow}>
              <Feather
                name="clock"
                size={12}
                color={colors.textMuted}
              />
              <Text style={styles.queueText}>
                {pending} na fila local
              </Text>
            </View>
          ) : null}
          {status ? (
            <Text style={styles.status}>{status}</Text>
          ) : null}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  modebar: {
    flexDirection: "row",
    gap: 6,
    backgroundColor: colors.card2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    padding: 4,
  },
  mode: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
    borderRadius: radius.pill,
  },
  modeOn: { backgroundColor: colors.primary },
  modeTxt: {
    fontFamily: fonts.uiSemi,
    fontSize: 13,
    color: colors.textMuted,
  },
  modeTxtOn: { color: colors.primaryText },

  hint: {
    fontFamily: fonts.ui,
    color: colors.textMuted,
    fontSize: 13,
  },
  input: {
    minHeight: 120,
    textAlignVertical: "top",
  },
  sensitiveToggle: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
  },
  sensitiveToggleOn: {
    borderColor: "rgba(201,169,126,0.5)",
    backgroundColor: colors.primarySoft,
  },
  sensitiveText: {
    fontFamily: fonts.mono,
    fontSize: 10.5,
    color: colors.textMuted,
  },
  reply: {
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "center",
  },
  replyText: {
    flex: 1,
    fontFamily: fonts.ui,
    color: colors.text,
    fontSize: 15,
    lineHeight: 21,
  },
  queueRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: -spacing.xs,
  },
  queueText: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
  },
  status: {
    fontFamily: fonts.ui,
    fontSize: 12.5,
    color: colors.textMuted,
    marginTop: -spacing.xs,
  },

  sessionFields: {
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  pendingSessions: {
    gap: spacing.xs,
    marginBottom: spacing.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.card2,
  },
  pendingTitle: {
    fontFamily: fonts.mono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 1,
    color: colors.textMuted,
  },
  pendingSession: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  pendingSessionText: {
    flex: 1,
    fontFamily: fonts.ui,
    fontSize: 13,
    color: colors.text,
  },
  pagesRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  timerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
  },
  timerText: {
    fontFamily: fonts.mono,
    fontSize: 18,
    color: colors.primary,
  },
  recordingDot: {
    width: 7,
    height: 7,
    borderRadius: 7,
    backgroundColor: colors.textMuted,
    marginLeft: spacing.sm,
  },
  recordingDotOn: { backgroundColor: "#DE8A7A" },
  recordingText: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.7,
  },
  interim: {
    fontFamily: fonts.ui,
    fontSize: 13,
    lineHeight: 18,
    color: colors.textMuted,
    fontStyle: "italic",
    paddingHorizontal: spacing.sm,
  },
  bookHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  bookTitle: {
    flex: 1,
    fontFamily: fonts.serif,
    fontSize: 17,
    color: colors.text,
  },
  bookCount: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
    marginLeft: "auto",
  },
  item: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  itemHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 4,
  },
  itemKind: {
    fontFamily: fonts.mono,
    fontSize: 9.5,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  itemText: {
    fontFamily: fonts.ui,
    fontSize: 14.5,
    color: colors.text,
    lineHeight: 20,
  },

  addRow: {
    flexDirection: "row",
    gap: spacing.sm,
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  addBtn: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  compileMeta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  compileHint: {
    flex: 1,
    fontFamily: fonts.ui,
    fontSize: 11,
    lineHeight: 16,
    color: colors.textMuted,
  },
  discardText: {
    fontFamily: fonts.mono,
    fontSize: 10.5,
    color: "#DE8A7A",
  },
});
