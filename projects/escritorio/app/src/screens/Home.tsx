import { Feather } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AppState,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  Abertura,
  Digest,
  Pontos,
  getAbertura,
  getDigest,
  getPontos,
  getTriagem,
  listAnkiCards,
} from "../api";
import { listPendingReadingSessions } from "../readingApi";
import { actionForAt, HomeSignals, nextAgendaAt } from "../homeAction";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { Badge, ProgressBar, SectionHeader, Skeleton } from "../ui";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Bom dia";
  if (hour >= 12 && hour < 18) return "Boa tarde";
  return "Boa noite";
}

function dateLabel(): string {
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(new Date());
}

export default function Home({ onOpenTab }: { onOpenTab?: (tab: string) => void }) {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [abertura, setAbertura] = useState<Abertura | null>(null);
  const [points, setPoints] = useState<Pontos | null>(null);
  const [signals, setSignals] = useState<HomeSignals>({ staging: null, anki: null, reading: null });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loaded, setLoaded] = useState<Set<string>>(new Set());
  const [failures, setFailures] = useState<Set<string>>(new Set());
  const [, setClockTick] = useState(() => Date.now());
  const loadEpoch = useRef(0);

  const load = useCallback(async (refresh = false) => {
    const epoch = ++loadEpoch.current;
    refresh ? setRefreshing(true) : setLoading(true);
    setFailures(new Set());

    const within = <T,>(promise: Promise<T>): Promise<T> =>
      Promise.race([
        promise,
        new Promise<T>((_, reject) => setTimeout(() => reject(new Error("timeout")), 6000)),
      ]);
    const run = async <T,>(key: string, promise: Promise<T>, apply: (value: T) => void) => {
      try {
        const value = await within(promise);
        if (loadEpoch.current !== epoch) return;
        apply(value);
        setLoaded((current) => new Set(current).add(key));
      } catch {
        if (loadEpoch.current !== epoch) return;
        setFailures((current) => new Set(current).add(key));
      } finally {
        if (loadEpoch.current === epoch && key === "abertura") setLoading(false);
      }
    };

    await Promise.all([
      run("digest", getDigest(), setDigest),
      run("abertura", getAbertura(), (value) => {
        setAbertura(value);
        // Modo Retorno: o sinal precisa chegar ao actionForAt, que decide a Home.
        setSignals((current) => ({ ...current, dias_ausente: value.dias_ausente ?? 0 }));
      }),
      run("points", getPontos(), setPoints),
      run("triagem", getTriagem(), (value) => setSignals((current) => ({ ...current, staging: value.n }))),
      run("anki", listAnkiCards("sugerido"), (value) => setSignals((current) => ({ ...current, anki: value.length }))),
      run("reading", listPendingReadingSessions(), (value) => setSignals((current) => ({ ...current, reading: value.sessions.length }))),
    ]);
    if (loadEpoch.current === epoch) {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") load(true);
    });
    return () => subscription.remove();
  }, [load]);

  useEffect(() => {
    const timer = setInterval(() => setClockTick(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const partial = failures.size > 0;
  const action = actionForAt(abertura, signals);
  const focus = (digest?.tasks ?? []).slice(0, 3);
  const routineDone = abertura?.rotinas_manha.filter((routine) => routine.feito).length ?? 0;
  const routineTotal = abertura?.rotinas_manha.length ?? 0;
  const cycleProgress = points?.ciclo.meta
    ? points.ciclo.pontos / points.ciclo.meta
    : 0;
  const nextAgenda = abertura
    ? nextAgendaAt(
        abertura.hoje.horarios,
        abertura.hoje.calendario,
        abertura.data,
      )
    : [];

  return (
    <View style={styles.root}>
      <View pointerEvents="none" style={styles.glowTop} />
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={colors.primary} />}
      >
        <View style={styles.topline}>
          <View>
            <Text style={styles.date}>{dateLabel()}</Text>
            <Text style={styles.greeting}>{greeting()}, <Text style={styles.name}>Leo.</Text></Text>
          </View>
          <Pressable accessibilityLabel="Abrir revisão" onPress={() => onOpenTab?.("revisao")} style={styles.levelSeal}>
            <Text style={styles.levelSmall}>NÍVEL</Text>
            <Text style={styles.levelNumber}>{loaded.has("points") ? points?.nivel ?? 0 : "—"}</Text>
          </Pressable>
        </View>

        {partial ? (
          <Pressable onPress={() => load(true)} style={styles.partial}>
            <Feather name="cloud-off" size={12} color={colors.textMuted} />
            <Text style={styles.partialText}>alguns dados não responderam · atualizar</Text>
          </Pressable>
        ) : null}

        {loading ? (
          <>
            <Skeleton height={176} />
            <Skeleton height={84} />
            <Skeleton height={160} />
          </>
        ) : (
          <>
            <Pressable onPress={() => onOpenTab?.(action.target)} style={({ pressed }) => pressed && { opacity: 0.92 }}>
              <LinearGradient colors={["#27231D", "#171B1D", "#12161B"]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.hero}>
                <View style={styles.heroIcon}><Feather name={action.icon as keyof typeof Feather.glyphMap} size={20} color={colors.primary} /></View>
                <Text style={styles.heroEyebrow}>{action.eyebrow}</Text>
                <Text style={styles.heroTitle}>{action.title}</Text>
                <Text style={styles.heroSubtitle}>{action.subtitle}</Text>
                <View style={styles.heroFoot}>
                  <Text style={styles.heroAction}>abrir agora</Text>
                  <View style={styles.arrow}><Feather name="arrow-up-right" size={18} color={colors.primaryText} /></View>
                </View>
              </LinearGradient>
            </Pressable>

            <View style={styles.metricsRow}>
              <Pressable onPress={() => onOpenTab?.("rotinas")} style={styles.metric}>
                <Text style={styles.metricLabel}>RITMOS</Text>
                <Text style={styles.metricValue}>{loaded.has("abertura") ? routineDone : "—"}<Text style={styles.metricMuted}>/{loaded.has("abertura") ? routineTotal : "—"}</Text></Text>
                <ProgressBar value={routineTotal ? routineDone / routineTotal : 0} color={colors.success} />
              </Pressable>
              <Pressable onPress={() => onOpenTab?.("revisao")} style={styles.metric}>
                <Text style={styles.metricLabel}>CICLO</Text>
                <Text style={styles.metricValue}>{loaded.has("points") ? `S${points?.ciclo.semana ?? 1}` : "—"}<Text style={styles.metricMuted}>/{loaded.has("points") ? points?.ciclo.de ?? 12 : "—"}</Text></Text>
                <ProgressBar value={cycleProgress} />
              </Pressable>
              <Pressable onPress={() => onOpenTab?.("tarefas")} style={styles.metric}>
                <Text style={styles.metricLabel}>COBRANÇAS</Text>
                <Text style={styles.metricValue}>{loaded.has("digest") ? digest?.count ?? 0 : "—"}</Text>
                <Text style={styles.metricHint}>no radar</Text>
              </Pressable>
            </View>

            <View style={styles.section}>
              <SectionHeader eyebrow="direção" title="Foco de hoje" action="ver tarefas" onAction={() => onOpenTab?.("tarefas")} />
              {focus.length ? focus.map((task, index) => (
                <Pressable key={task.id} onPress={() => onOpenTab?.(`tarefa:${task.id}`)} style={styles.focusRow}>
                  <Text style={styles.focusIndex}>0{index + 1}</Text>
                  <View style={[styles.focusEdge, { backgroundColor: areaColor(task.area) }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.focusTitle} numberOfLines={2}>{task.name}</Text>
                    <Text style={styles.focusMeta}>{task.area} · {task.due ?? task.status}</Text>
                  </View>
                  <Feather name="chevron-right" size={17} color={colors.textMuted} />
                </Pressable>
              )) : loaded.has("digest") ? (
                <Pressable onPress={() => onOpenTab?.("capturar")} style={styles.clearState}>
                  <View style={styles.clearIcon}><Feather name="wind" size={19} color={colors.success} /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.clearTitle}>Sem urgência artificial.</Text>
                    <Text style={styles.clearText}>Capture a próxima ação quando ela existir.</Text>
                  </View>
                </Pressable>
              ) : (
                <View style={styles.unavailableState}>
                  <Feather name={failures.has("digest") ? "cloud-off" : "loader"} size={17} color={colors.textMuted} />
                  <Text style={styles.agendaEmpty}>{failures.has("digest") ? "tarefas indisponíveis agora" : "carregando prioridades…"}</Text>
                </View>
              )}
            </View>

            <View style={styles.section}>
              <SectionHeader eyebrow="tempo" title="Agenda curta" action="abrir agenda" onAction={() => onOpenTab?.("abertura")} />
              <View style={styles.agendaCard}>
                {nextAgenda.length ? nextAgenda.map((item, index) => (
                  <View key={`${item.time}-${item.title}-${index}`} style={[styles.agendaRow, index > 0 && styles.agendaBorder]}>
                    <Text style={styles.agendaTime}>{item.time}</Text>
                    <View style={styles.agendaLine} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.agendaTitle} numberOfLines={1}>{item.title}</Text>
                      <Text style={styles.agendaSource}>{item.source}</Text>
                    </View>
                  </View>
                )) : loaded.has("abertura") ? (
                  <View style={styles.agendaRow}>
                    <Text style={styles.agendaTime}>—</Text>
                    <View style={styles.agendaLine} />
                    <Text style={styles.agendaEmpty}>nenhum horário confirmado</Text>
                  </View>
                ) : (
                  <View style={styles.agendaRow}>
                    <Text style={styles.agendaTime}>—</Text>
                    <View style={styles.agendaLine} />
                    <Text style={styles.agendaEmpty}>{failures.has("abertura") ? "agenda indisponível agora" : "carregando agenda…"}</Text>
                  </View>
                )}
              </View>
            </View>

            {((signals.staging ?? 0) + (signals.anki ?? 0) + (signals.reading ?? 0)) > 0 ? (
              <View style={styles.section}>
                <SectionHeader eyebrow="filas" title="Em espera" />
                <View style={styles.badges}>
                  {(signals.staging ?? 0) > 0 ? <Pressable onPress={() => onOpenTab?.("triagem")}><Badge label="triagem" value={signals.staging ?? undefined} color={colors.info} /></Pressable> : null}
                  {(signals.anki ?? 0) > 0 ? <Pressable onPress={() => onOpenTab?.("revisao")}><Badge label="Anki" value={signals.anki ?? undefined} color={colors.lilac} /></Pressable> : null}
                  {(signals.reading ?? 0) > 0 ? <Pressable onPress={() => onOpenTab?.("leitura")}><Badge label="leituras" value={signals.reading ?? undefined} color={colors.primary} /></Pressable> : null}
                </View>
              </View>
            ) : null}

            <View style={styles.section}>
              <SectionHeader eyebrow="sistema" title="Ferramentas" />
              <View style={styles.tools}>
                {[
                  // "Agenda" abria a Abertura: o rótulo mentia. Não existe tela de
                  // calendário ainda (GET /agenda segue órfão) — até existir, o nome
                  // diz o que o botão faz.
                  ["sunrise", "Abertura", "abertura", colors.info],
                  ["inbox", "Triagem", "triagem", colors.amber],
                  ["repeat", "Ritmos", "rotinas", colors.success],
                  ["trending-down", "Reduzir", "habitos", colors.info],
                  ["compass", "Revisão", "revisao", colors.primary],
                  ["layers", "Edificação", "edificacao", colors.lilac],
                  ["sunset", "Shutdown", "shutdown", colors.primary],
                  ["moon", "Fechar dia", "fechar", colors.info],
                  ["settings", "Ajustes", "settings", colors.textMuted],
                ].map(([icon, label, target, color]) => (
                  <Pressable key={label} onPress={() => onOpenTab?.(target)} style={styles.tool}>
                    <View style={[styles.toolIcon, { backgroundColor: `${color}19` }]}>
                      <Feather name={icon as keyof typeof Feather.glyphMap} size={18} color={color} />
                    </View>
                    <Text style={styles.toolLabel}>{label}</Text>
                    <Feather name="arrow-up-right" size={14} color={colors.textMuted} />
                  </Pressable>
                ))}
              </View>
            </View>
          </>
        )}
      </ScrollView>

      <Pressable style={styles.captureDock} onPress={() => onOpenTab?.("capturar")}>
        <View style={styles.capturePlus}><Feather name="plus" size={19} color={colors.primaryText} /></View>
        <View style={{ flex: 1 }}>
          <Text style={styles.captureLabel}>captura universal</Text>
          <Text style={styles.captureHint}>Fala ou digita. Organiza depois.</Text>
        </View>
        <Feather name="mic" size={19} color={colors.primary} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  glowTop: { position: "absolute", top: -120, right: -90, width: 270, height: 270, borderRadius: 160, backgroundColor: "rgba(222,184,120,0.055)" },
  content: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: 128 },
  topline: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.lg },
  date: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, textTransform: "uppercase", letterSpacing: 1.2 },
  greeting: { fontFamily: fonts.serif, fontSize: 30, color: colors.text, letterSpacing: -0.7, marginTop: 4 },
  name: { color: colors.primary },
  levelSeal: { width: 50, height: 50, borderRadius: 25, borderWidth: 1, borderColor: "rgba(222,184,120,0.35)", backgroundColor: colors.primarySoft, alignItems: "center", justifyContent: "center" },
  levelSmall: { fontFamily: fonts.mono, fontSize: 7, color: colors.primary, letterSpacing: 1 },
  levelNumber: { fontFamily: fonts.serif, fontSize: 18, color: colors.text, lineHeight: 20 },
  partial: { flexDirection: "row", alignItems: "center", gap: 7, marginBottom: spacing.md },
  partialText: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 11.5 },
  hero: { minHeight: 188, borderRadius: radius.xl, padding: spacing.lg, borderWidth: 1, borderColor: "rgba(222,184,120,0.19)", overflow: "hidden" },
  heroIcon: { position: "absolute", top: 16, right: 16, width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(222,184,120,0.1)", borderWidth: 1, borderColor: "rgba(222,184,120,0.18)" },
  heroEyebrow: { fontFamily: fonts.mono, fontSize: 10, color: colors.primary, letterSpacing: 1.6, textTransform: "uppercase" },
  heroTitle: { fontFamily: fonts.serif, fontSize: 27, lineHeight: 31, color: colors.text, letterSpacing: -0.6, marginTop: spacing.lg, maxWidth: "82%" },
  heroSubtitle: { fontFamily: fonts.ui, fontSize: 13.5, lineHeight: 19, color: colors.textMuted, marginTop: 6, maxWidth: "88%" },
  heroFoot: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: "auto" },
  heroAction: { fontFamily: fonts.uiSemi, fontSize: 12.5, color: colors.primary },
  arrow: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center", backgroundColor: colors.primary },
  metricsRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  metric: { flex: 1, minHeight: 92, borderRadius: radius.lg, padding: spacing.md, backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border },
  metricLabel: { fontFamily: fonts.mono, fontSize: 8.5, letterSpacing: 1.1, color: colors.textMuted },
  metricValue: { fontFamily: fonts.serif, fontSize: 21, color: colors.text, marginTop: 8, marginBottom: 8 },
  metricMuted: { color: colors.textMuted, fontSize: 13 },
  metricHint: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 10.5 },
  section: { marginTop: spacing.xl },
  focusRow: { minHeight: 72, flexDirection: "row", alignItems: "center", gap: 10, borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: spacing.sm },
  focusIndex: { width: 22, fontFamily: fonts.mono, fontSize: 10, color: colors.textMuted },
  focusEdge: { width: 3, height: 38, borderRadius: 3 },
  focusTitle: { fontFamily: fonts.uiSemi, color: colors.text, fontSize: 14.5, lineHeight: 18 },
  focusMeta: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 11.5, marginTop: 4 },
  clearState: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, backgroundColor: colors.card2, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border },
  clearIcon: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(113,180,154,0.11)" },
  clearTitle: { fontFamily: fonts.uiSemi, color: colors.text, fontSize: 14 },
  clearText: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 11.5, marginTop: 3 },
  unavailableState: { minHeight: 68, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.md, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, backgroundColor: colors.card2 },
  agendaCard: { backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, paddingHorizontal: spacing.md },
  agendaRow: { minHeight: 66, flexDirection: "row", alignItems: "center", gap: spacing.md },
  agendaBorder: { borderTopWidth: 1, borderTopColor: colors.border },
  agendaTime: { width: 38, fontFamily: fonts.mono, fontSize: 11, color: colors.primary },
  agendaLine: { width: 1, height: 30, backgroundColor: colors.border },
  agendaTitle: { fontFamily: fonts.uiSemi, fontSize: 13.5, color: colors.text },
  agendaSource: { fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted, marginTop: 3, textTransform: "uppercase" },
  agendaEmpty: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tools: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tool: { width: "48.5%", minHeight: 66, flexDirection: "row", alignItems: "center", gap: 9, backgroundColor: colors.card2, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.md },
  toolIcon: { width: 34, height: 34, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  toolLabel: { flex: 1, fontFamily: fonts.uiSemi, color: colors.text, fontSize: 12.5 },
  captureDock: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: spacing.md, minHeight: 62, flexDirection: "row", alignItems: "center", gap: 11, backgroundColor: "#191D22", borderWidth: 1, borderColor: "rgba(222,184,120,0.23)", borderRadius: radius.xl, padding: 9, paddingRight: spacing.lg },
  capturePlus: { width: 42, height: 42, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: colors.primary },
  captureLabel: { fontFamily: fonts.mono, color: colors.primary, fontSize: 9, letterSpacing: 1, textTransform: "uppercase" },
  captureHint: { fontFamily: fonts.ui, color: colors.text, fontSize: 12.5, marginTop: 2 },
});
