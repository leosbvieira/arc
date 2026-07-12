import { Feather } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import {
  Alert,
  AppState,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { capture, logSession } from "../api";
import {
  createCaptureClientKey,
  enqueue,
  flush,
  pendingCount,
} from "../captureQueue";
import { colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, Field } from "../ui";

type Mode = "captura" | "leitura";
type Item = { id: string; kind: string; text: string; anki?: boolean };

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

export default function Capture() {
  const [mode, setMode] = useState<Mode>("captura");

  // captura livre
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
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
          payload: { text: t, client_key: clientKey },
          ts,
        });
        setText("");
        setPending(await pendingCount());
        setStatus(
          "sem conexão — guardado no aparelho, reenvio automático",
        );
        return;
      }

      const r = await capture(t, undefined, clientKey);
      setReply(r);
      setText("");
      setPending(await pendingCount());
    } catch {
      // A mesma client_key usada no primeiro POST acompanha o retry. Se o BFF
      // recebeu a captura e só a resposta se perdeu, ele devolve o id existente.
      await enqueue({
        kind: "capture",
        payload: { text: t, client_key: clientKey },
        ts,
      });
      setText("");
      setPending(await pendingCount());
      setStatus(
        "sem conexão — guardado no aparelho, reenvio automático",
      );
    } finally {
      setBusy(false);
    }
  }

  function onAdd() {
    if (!entry.trim()) return;
    const p = parse(entry);
    if (p.book) {
      setBook(p.book);
    } else if (p.text) {
      setItems((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          kind: p.kind!,
          text: p.text,
        },
      ]);
    }
    setEntry("");
  }

  function toggleAnki(id: string) {
    setItems((prev) =>
      prev.map((it) =>
        it.id === id ? { ...it, anki: !it.anki } : it,
      ),
    );
  }

  const ankiCount = items.filter((it) => it.anki).length;

  function sessionText(): string {
    return items
      .map(
        (it) =>
          `${it.kind}: ${it.text}${it.anki ? " [★ anki]" : ""}`,
      )
      .join("\n");
  }

  function paginasLidas(): number | null {
    const initialText = pageStart.trim();
    const finalText = pageEnd.trim();
    if (!initialText || !finalText) return null;

    const initial = Number(initialText);
    const final = Number(finalText);
    if (!Number.isFinite(initial) || !Number.isFinite(final)) {
      return null;
    }
    return final - initial;
  }

  async function compilar() {
    if (compiling || (!sessionStart && !items.length)) return;

    const ts = Date.now();
    const sessionKey = createSessionKey(ts);
    const duracao_s = sessionStart
      ? Math.round((ts - sessionStart) / 1000)
      : 0;
    const payload = {
      tipo: "leitura",
      livro: book.trim() || null,
      paginas: paginasLidas(),
      duracao_s,
      notas: sessionText(),
      session_key: sessionKey,
    };

    setCompiling(true);
    setStatus("");
    try {
      await logSession(payload);
      setSessionStart(null);
      setItems([]);
      setPageStart("");
      setPageEnd("");
      Alert.alert("Sessão compilada", "Sessão registrada.");
    } catch {
      await enqueue({
        kind: "session",
        payload,
        ts,
      });
      setSessionStart(null);
      setItems([]);
      setPageStart("");
      setPageEnd("");
      setStatus("sessão guardada — reenvio automático");
      setPending(await pendingCount());
    } finally {
      setCompiling(false);
    }
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
          <View style={styles.sessionFields}>
            <Field
              value={book}
              onChangeText={setBook}
              placeholder="Livro"
            />
            <View style={styles.pagesRow}>
              <Field
                style={{ flex: 1 }}
                value={pageStart}
                onChangeText={setPageStart}
                placeholder="Página inicial"
                keyboardType="number-pad"
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
              title="▶ iniciar sessão"
              variant="ghost"
              onPress={() => setSessionStart(Date.now())}
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
              </View>
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
              {ankiCount ? ` · ★${ankiCount}` : ""}
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
                    <Pressable
                      onPress={() => toggleAnki(it.id)}
                      hitSlop={8}
                      style={{ marginLeft: "auto" }}
                    >
                      <Feather
                        name="star"
                        size={15}
                        color={
                          it.anki
                            ? colors.primary
                            : colors.textMuted
                        }
                      />
                    </Pressable>
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
});
