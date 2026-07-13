import { Feather } from "@expo/vector-icons";
import { useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";

import { chatSend } from "../api";
import { areaColor, colors, fonts, radius, spacing } from "../theme";

type Msg = { from: "me" | "ai" | "ground"; text?: string; soul?: string; k?: string; v?: string };
type Conv = { id: string; mode: string; title: string; time: string; sub: string; msgs: Msg[] };

// Uma cor por modo. A paleta mudou na Task 6 (10 áreas normativas): "Pessoal" saiu, então
// Capturas passa a usar o cinza de Staging (para onde as capturas vão). Conselho deixa de
// usar "Trabalho" — que é o MESMO bronze do colors.primary/Mentor e colava os dois — e vai
// pro azul "Carreira" (estratégico), distinto de Mentor (bronze) e Capturas (cinza).
const MODE_COLOR: Record<string, string> = {
  Mentor: colors.primary,
  Capturas: areaColor("Staging"),
  Conselho: areaColor("Carreira"),
};

const CONVS: Conv[] = [
  {
    id: "mentor",
    mode: "Mentor",
    title: "nova conversa",
    time: "agora",
    sub: "sessão local · não persistida",
    msgs: [],
  },
  {
    id: "capturas",
    mode: "Capturas",
    title: "nova conversa",
    time: "agora",
    sub: "sessão local · não persistida",
    msgs: [],
  },
  {
    id: "conselho",
    mode: "Conselho",
    title: "nova conversa",
    time: "agora",
    sub: "sessão local · não persistida",
    msgs: [],
  },
];

const GROUPS = [
  { group: "Modos", ids: ["mentor", "capturas", "conselho"] },
];

function Sidebar({
  convs,
  activeId,
  onPick,
}: {
  convs: Record<string, Conv>;
  activeId: string;
  onPick: (id: string) => void;
}) {
  return (
    <View style={styles.railInner}>
      <View style={styles.rtop}>
        <Text style={styles.railBrand}>Conversas</Text>
        <View style={styles.newBtn}>
          <Feather name="plus" size={14} color={colors.primaryText} />
          <Text style={styles.newTxt}>Nova</Text>
        </View>
      </View>
      <View style={styles.search}>
        <Feather name="search" size={15} color={colors.textMuted} />
        <Text style={styles.searchTxt}>buscar conversa…</Text>
      </View>
      <ScrollView showsVerticalScrollIndicator={false}>
        {GROUPS.map((g) => (
          <View key={g.group}>
            <Text style={styles.grp}>{g.group}</Text>
            {g.ids.map((id) => {
              const c = convs[id];
              return (
                <Pressable
                  key={id}
                  onPress={() => onPick(id)}
                  style={[styles.ci, id === activeId && styles.ciOn]}
                >
                  <View style={[styles.cd, { backgroundColor: MODE_COLOR[c.mode] }]} />
                  <View style={{ flex: 1 }}>
                    <View style={styles.ctop}>
                      <Text style={[styles.cmode, { color: MODE_COLOR[c.mode] }]}>{c.mode}</Text>
                      <Text style={styles.ctime}>{c.time}</Text>
                    </View>
                    <Text style={styles.ctitle} numberOfLines={1}>
                      {c.title}
                    </Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

function Conversation({
  conv,
  draft,
  onDraft,
  onSend,
  onMenu,
  showMenu,
  sending,
}: {
  conv: Conv;
  draft: string;
  onDraft: (t: string) => void;
  onSend: () => void;
  onMenu?: () => void;
  showMenu?: boolean;
  sending?: boolean;
}) {
  const accent = MODE_COLOR[conv.mode] ?? colors.primary;
  const hasDraft = draft.trim().length > 0;
  const scrollRef = useRef<ScrollView>(null);
  return (
    <View style={{ flex: 1 }}>
      <View style={styles.phead}>
        {showMenu ? (
          <Pressable onPress={onMenu} hitSlop={8} style={{ marginRight: 6 }}>
            <Feather name="menu" size={20} color={colors.text} />
          </Pressable>
        ) : null}
        <View style={[styles.pdot, { backgroundColor: accent }]} />
        <Text style={styles.ptitle}>{conv.mode}</Text>
        <Text style={styles.psub}>{conv.sub}</Text>
      </View>
      <ScrollView
        ref={scrollRef}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
        contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}
        showsVerticalScrollIndicator={false}
      >
        {conv.msgs.map((m, i) => {
          if (m.from === "me") {
            return (
              <View key={i} style={styles.me}>
                <Text style={styles.meTxt}>{m.text}</Text>
              </View>
            );
          }
          if (m.from === "ground") {
            return (
              <View key={i} style={styles.ground}>
                <Text style={styles.groundK}>{m.k}</Text>
                <Text style={styles.groundV}>{m.v}</Text>
              </View>
            );
          }
          return (
            <View key={i} style={styles.ai}>
              <Text style={styles.aiTxt}>
                {m.soul ? <Text style={styles.soul}>{m.soul} </Text> : null}
                {m.text}
              </Text>
            </View>
          );
        })}
        {sending ? (
          <View style={[styles.ai, styles.typing]}>
            <ActivityIndicator size="small" color={colors.textMuted} />
            <Text style={styles.typingTxt}>{conv.mode} está pensando…</Text>
          </View>
        ) : null}
      </ScrollView>
      <View style={styles.composer}>
        <TextInput
          style={styles.composerInput}
          value={draft}
          onChangeText={onDraft}
          onSubmitEditing={onSend}
          returnKeyType="send"
          blurOnSubmit={false}
          editable={!sending}
          placeholder={`Responder ${conv.mode.toLowerCase()}…`}
          placeholderTextColor={colors.textMuted}
        />
        <Pressable
          onPress={onSend}
          disabled={sending}
          style={[styles.mic, { backgroundColor: accent }, sending && { opacity: 0.6 }]}
        >
          {sending ? (
            <ActivityIndicator size="small" color={colors.primaryText} />
          ) : (
            <Feather name={hasDraft ? "arrow-up" : "mic"} size={20} color={colors.primaryText} />
          )}
        </Pressable>
      </View>
    </View>
  );
}

export default function Chat() {
  const { width } = useWindowDimensions();
  const wide = width >= 720;
  const [activeId, setActiveId] = useState("mentor");
  const [drawer, setDrawer] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [convs, setConvs] = useState<Record<string, Conv>>(() =>
    Object.fromEntries(CONVS.map((c) => [c.id, c]))
  );

  const active = convs[activeId];

  async function send() {
    const t = draft.trim();
    if (!t || sending) return;
    const id = activeId;
    const mode = convs[id].mode;
    setConvs((prev) => ({
      ...prev,
      [id]: { ...prev[id], msgs: [...prev[id].msgs, { from: "me", text: t }] },
    }));
    setDraft("");
    setSending(true);
    try {
      const reply = await chatSend(t, mode);
      setConvs((prev) => ({
        ...prev,
        [id]: { ...prev[id], msgs: [...prev[id].msgs, { from: "ai", text: reply }] },
      }));
    } catch (e: any) {
      setConvs((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          msgs: [...prev[id].msgs, { from: "ai", text: "⚠ " + (e?.message ?? "não consegui responder") }],
        },
      }));
    } finally {
      setSending(false);
    }
  }

  const convo = useMemo(
    () => (
      <Conversation
        conv={active}
        draft={draft}
        onDraft={setDraft}
        onSend={send}
        sending={sending}
        showMenu={!wide}
        onMenu={() => setDrawer(true)}
      />
    ),
    [active, draft, wide, sending]
  );

  if (wide) {
    return (
      <View style={styles.wide}>
        <View style={styles.rail}>
          <Sidebar convs={convs} activeId={activeId} onPick={setActiveId} />
        </View>
        {convo}
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      {convo}
      {drawer ? (
        <>
          <Pressable style={styles.scrim} onPress={() => setDrawer(false)} />
          <View style={styles.drawer}>
            <Sidebar
              convs={convs}
              activeId={activeId}
              onPick={(id) => {
                setActiveId(id);
                setDrawer(false);
              }}
            />
          </View>
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wide: { flex: 1, flexDirection: "row", backgroundColor: colors.surface },
  rail: { width: 262, borderRightWidth: 1, borderRightColor: colors.border, backgroundColor: colors.bg },

  railInner: { flex: 1, paddingHorizontal: 12, paddingTop: 14 },
  rtop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 4, paddingBottom: 12 },
  railBrand: { fontFamily: fonts.serif, fontSize: 22, color: colors.text },
  newBtn: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.primary, paddingHorizontal: 11, paddingVertical: 7, borderRadius: radius.pill },
  newTxt: { fontFamily: fonts.uiSemi, fontSize: 12, color: colors.primaryText },
  search: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border, borderRadius: 11, paddingHorizontal: 11, paddingVertical: 9 },
  searchTxt: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted },
  grp: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.4, textTransform: "uppercase", color: colors.textMuted, marginTop: 14, marginBottom: 6, marginLeft: 4 },
  ci: { flexDirection: "row", gap: 9, alignItems: "flex-start", padding: 8, borderRadius: 10 },
  ciOn: { backgroundColor: "rgba(255,255,255,0.05)" },
  cd: { width: 7, height: 7, borderRadius: 9, marginTop: 5 },
  ctop: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 6 },
  cmode: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: 1, textTransform: "uppercase" },
  ctime: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted },
  ctitle: { fontFamily: fonts.ui, fontSize: 13, color: colors.text, marginTop: 2 },

  phead: { flexDirection: "row", alignItems: "center", gap: 9, paddingHorizontal: spacing.lg, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border },
  pdot: { width: 9, height: 9, borderRadius: 9, backgroundColor: colors.primary },
  ptitle: { fontFamily: fonts.uiSemi, fontSize: 15, color: colors.text },
  psub: { fontFamily: fonts.mono, fontSize: 10, color: colors.textMuted, marginLeft: "auto", letterSpacing: 0.4 },

  me: { alignSelf: "flex-end", maxWidth: "88%", backgroundColor: colors.userBubble, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 15, paddingVertical: 11, borderTopLeftRadius: 18, borderTopRightRadius: 18, borderBottomRightRadius: 5, borderBottomLeftRadius: 18 },
  meTxt: { fontFamily: fonts.ui, fontSize: 14, color: colors.text },
  ai: { alignSelf: "flex-start", maxWidth: "92%", backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 16, paddingVertical: 13, borderTopLeftRadius: 18, borderTopRightRadius: 18, borderBottomRightRadius: 18, borderBottomLeftRadius: 5 },
  aiTxt: { fontFamily: fonts.ui, fontSize: 14.5, color: colors.text, lineHeight: 21 },
  typing: { flexDirection: "row", alignItems: "center", gap: 9 },
  typingTxt: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  soul: { fontFamily: fonts.serif, fontSize: 16, color: colors.text },
  ground: { alignSelf: "stretch", backgroundColor: colors.primarySoft, borderWidth: 1, borderColor: "rgba(201,169,126,0.3)", borderRadius: 13, paddingHorizontal: 14, paddingVertical: 10, marginTop: -4 },
  groundK: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1, textTransform: "uppercase", color: colors.primary },
  groundV: { fontFamily: fonts.serif, fontSize: 15, color: colors.text, marginTop: 3 },

  composer: { flexDirection: "row", alignItems: "center", gap: 10, margin: spacing.lg, marginTop: spacing.sm, backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, padding: 8, paddingLeft: 18 },
  composerInput: { flex: 1, fontFamily: fonts.ui, fontSize: 14, color: colors.text, paddingVertical: 0 },
  mic: { width: 42, height: 42, borderRadius: 99, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },

  scrim: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(4,4,6,0.6)" },
  drawer: { position: "absolute", top: 0, left: 0, bottom: 0, width: "86%", backgroundColor: colors.surface, borderRightWidth: 1, borderRightColor: colors.border, paddingTop: spacing.md },
});
