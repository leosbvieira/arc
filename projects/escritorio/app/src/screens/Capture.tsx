import { Feather } from "@expo/vector-icons";
import { useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { capture } from "../api";
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
  const after = () => (t.includes(":") ? t.slice(t.indexOf(":") + 1).trim() : t);
  if (l.startsWith("livro")) return { book: after(), text: "" };
  if (l.startsWith("cita")) return { kind: "citação", text: after() };
  if (l.startsWith("coment")) return { kind: "comentário", text: after() };
  if (l.startsWith("ideia")) return { kind: "ideia", text: after() };
  if (l.startsWith("coach")) return { kind: "coach", text: after() };
  return { kind: "comentário", text: t };
}

const SEED: Item[] = [
  { id: "s1", kind: "citação", text: "A verdadeira sabedoria está em reconhecer a própria ignorância." },
  { id: "s2", kind: "comentário", text: "Conversa com o que o Taleb fala de antifragilidade." },
];

export default function Capture() {
  const [mode, setMode] = useState<Mode>("captura");

  // captura livre
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  // sessão de leitura
  const [book, setBook] = useState("Antifrágil · p. 85");
  const [items, setItems] = useState<Item[]>(SEED);
  const [entry, setEntry] = useState("");
  const [compiling, setCompiling] = useState(false);

  async function onSend() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const r = await capture(text.trim());
      setReply(r);
      setText("");
    } catch (e: any) {
      Alert.alert("Erro", e?.message ?? "falhou");
    } finally {
      setBusy(false);
    }
  }

  function onAdd() {
    if (!entry.trim()) return;
    const p = parse(entry);
    if (p.book) setBook(p.book);
    else if (p.text) setItems((prev) => [...prev, { id: String(Date.now()), kind: p.kind!, text: p.text }]);
    setEntry("");
  }

  function toggleAnki(id: string) {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, anki: !it.anki } : it)));
  }

  const ankiCount = items.filter((it) => it.anki).length;

  function sessionText(): string {
    const lines = [`livro: ${book}`];
    for (const it of items) {
      lines.push(`${it.kind}: ${it.text}${it.anki ? " [★ anki]" : ""}`);
    }
    return lines.join("\n");
  }

  async function compilar() {
    if (!items.length || compiling) return;
    setCompiling(true);
    try {
      const r = await capture(sessionText(), "Leitura");
      Alert.alert("Sessão compilada", r);
    } catch (e: any) {
      Alert.alert("Compilar", e?.message ?? "falhou");
    } finally {
      setCompiling(false);
    }
  }

  return (
    <View style={{ flex: 1, paddingTop: spacing.sm }}>
      <View style={styles.modebar}>
        {(["captura", "leitura"] as Mode[]).map((m) => (
          <Pressable key={m} onPress={() => setMode(m)} style={[styles.mode, mode === m && styles.modeOn]}>
            <Text style={[styles.modeTxt, mode === m && styles.modeTxtOn]}>
              {m === "captura" ? "Captura" : "Leitura"}
            </Text>
          </Pressable>
        ))}
      </View>

      {mode === "captura" ? (
        <View style={{ gap: spacing.md, paddingTop: spacing.md }}>
          <Text style={styles.hint}>Fala ou digita — vira tarefa ou nota.</Text>
          <Field
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="ex.: cobrar Ana o relatório sexta"
            multiline
          />
          <AppButton title="Enviar" onPress={onSend} loading={busy} />
          {reply ? (
            <Card style={styles.reply}>
              <Feather name="check-circle" size={18} color={colors.success} />
              <Text style={styles.replyText}>{reply}</Text>
            </Card>
          ) : null}
        </View>
      ) : (
        <View style={{ flex: 1, paddingTop: spacing.md }}>
          <View style={styles.bookHead}>
            <Feather name="book" size={16} color={colors.primary} />
            <Text style={styles.bookTitle}>{book}</Text>
            <Text style={styles.bookCount}>
              {items.length} itens{ankiCount ? ` · ★${ankiCount}` : ""}
            </Text>
          </View>

          <ScrollView style={{ flex: 1, marginTop: spacing.sm }} showsVerticalScrollIndicator={false}>
            {items.map((it) => {
              const k = KIND[it.kind] ?? KIND["comentário"];
              return (
                <View key={it.id} style={[styles.item, { borderLeftColor: k.color }]}>
                  <View style={styles.itemHead}>
                    <Feather name={k.icon} size={12} color={k.color} />
                    <Text style={[styles.itemKind, { color: k.color }]}>{it.kind}</Text>
                    <Pressable onPress={() => toggleAnki(it.id)} hitSlop={8} style={{ marginLeft: "auto" }}>
                      <Feather name="star" size={15} color={it.anki ? colors.primary : colors.textMuted} />
                    </Pressable>
                  </View>
                  <Text style={styles.itemText}>{it.text}</Text>
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
            <Pressable onPress={onAdd} style={styles.addBtn}>
              <Feather name="plus" size={22} color={colors.primaryText} />
            </Pressable>
          </View>
          <AppButton title="Compilar sessão" variant="ghost" onPress={compilar} loading={compiling} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  modebar: { flexDirection: "row", gap: 6, backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, padding: 4 },
  mode: { flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: radius.pill },
  modeOn: { backgroundColor: colors.primary },
  modeTxt: { fontFamily: fonts.uiSemi, fontSize: 13, color: colors.textMuted },
  modeTxtOn: { color: colors.primaryText },

  hint: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 13 },
  input: { minHeight: 120, textAlignVertical: "top" },
  reply: { flexDirection: "row", gap: spacing.sm, alignItems: "center" },
  replyText: { flex: 1, fontFamily: fonts.ui, color: colors.text, fontSize: 15, lineHeight: 21 },

  bookHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  bookTitle: { fontFamily: fonts.serif, fontSize: 17, color: colors.text },
  bookCount: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted, marginLeft: "auto" },
  item: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 3, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm },
  itemHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 4 },
  itemKind: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1, textTransform: "uppercase" },
  itemText: { fontFamily: fonts.ui, fontSize: 14.5, color: colors.text, lineHeight: 20 },

  addRow: { flexDirection: "row", gap: spacing.sm, alignItems: "center", marginBottom: spacing.sm },
  addBtn: { width: 48, height: 48, borderRadius: radius.md, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
});
