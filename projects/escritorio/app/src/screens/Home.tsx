import Feather from "@expo/vector-icons/Feather";
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
import { milhar } from "../format";
import { valorDaAcao } from "../mesaView";
import { useParametros, useParams } from "../parametros";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { Badge, SectionHeader, SegmentBar, Skeleton } from "../ui";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "bom dia";
  if (hour >= 12 && hour < 18) return "boa tarde";
  return "boa noite";
}

function dateLabel(): string {
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(new Date());
}

export default function Home({ onOpenTab }: { onOpenTab?: (tab: string) => void }) {
  const fonte = useParametros();
  const params = useParams();
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
  // Indicador único, no nível do app: aparece sempre que a fonte NÃO é
  // `fresco` nem `cache` — ou seja, também em `indisponivel` (ex.: sessão
  // expirada num 401 que não desloga). Sem isso, o número embutido aparece
  // como se viesse do servidor, o defeito que esta fatia inteira mata.
  const avisoParametros =
    fonte.tipo === "padrao"
      ? "valores padrão · sem conexão"
      : fonte.tipo === "indisponivel"
        ? "valores padrão · sessão expirada"
        : null;
  const action = actionForAt(abertura, signals, params.ritos);
  // Preço do hero (tabela de tarifas, display-only). null = não desenha nada.
  const valorHero = valorDaAcao(action.target, params.tarifas);
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
        {/* Decisão 04=C: sai o glow de bronze do topo, entra o filete que
            assenta a saudação. */}
        <LinearGradient
          colors={["rgba(222,184,120,0.5)", "rgba(222,184,120,0)"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={styles.hairline}
        />

        {avisoParametros ? (
          <View style={styles.paramsAviso}>
            <Feather name="cloud-off" size={12} color={colors.textMuted} />
            <Text style={styles.paramsAvisoText}>{avisoParametros}</Text>
          </View>
        ) : null}

        {partial ? (
          <Pressable onPress={() => load(true)} style={styles.partial}>
            <Feather name="cloud-off" size={12} color={colors.textMuted} />
            <Text style={styles.partialText}>alguns dados não responderam · atualizar</Text>
          </Pressable>
        ) : null}

        {/* Saldo do placar: só aparece quando o points carregou de verdade —
            falha de rede nunca vira saldo zero. Mono porque o número re-soma
            à vista quando a Home recarrega no AppState "active". */}
        {loaded.has("points") && points ? (
          <View style={styles.saldoCard}>
            <View style={styles.saldoRow}>
              <Text style={styles.saldo}>
                {milhar(points.saldo_total)}
                <Text style={styles.saldoPts}> PTS</Text>
              </Text>
              <Text style={styles.saldoCiclo}>
                CICLO {points.ciclo.indice} · S{points.ciclo.semana}/{points.ciclo.de}
              </Text>
            </View>
            <View style={{ marginTop: spacing.md }}>
              <SegmentBar value={cycleProgress} />
            </View>
          </View>
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
              <LinearGradient colors={["#1B1712", "#12151A", "#0E1116"]} locations={[0, 0.6, 1]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.hero}>
                {/* O relógio do A voltou ao canto (05=C): o herói é de um bronze
                    só — o CTA — então o chip não troca de ícone por ação. */}
                <View style={styles.heroIcon}><Feather name="clock" size={16} color={colors.primary} /></View>
                <Text style={styles.heroEyebrow}>{action.eyebrow}</Text>
                <Text style={styles.heroTitle}>{action.title}</Text>
                <Text style={styles.heroSubtitle}>{action.subtitle}</Text>
                <View style={styles.heroFoot}>
                  <View style={styles.heroCta}>
                    <Text style={styles.heroCtaText}>Abrir agora</Text>
                    <Feather name="arrow-up-right" size={12} color={colors.primaryText} />
                  </View>
                  {valorHero !== null ? <Text style={styles.heroValue}>vale +{valorHero}</Text> : null}
                </View>
              </LinearGradient>
            </Pressable>

            <View style={styles.metricsRow}>
              <Pressable onPress={() => onOpenTab?.("rotinas")} style={styles.metric}>
                <Text style={styles.metricLabel}>RITMOS</Text>
                <Text style={styles.metricValue}>{loaded.has("abertura") ? routineDone : "—"}<Text style={styles.metricMuted}>/{loaded.has("abertura") ? routineTotal : "—"}</Text></Text>
                {/* 09=C: barra segmentada sálvia com o próximo segmento vazado. */}
                <SegmentBar
                  value={routineTotal ? routineDone / routineTotal : 0}
                  segments={routineTotal > 0 ? routineTotal : 8}
                  tone="sage"
                  outlineNext
                />
              </Pressable>
              <Pressable
                onPress={() =>
                  focus[0] ? onOpenTab?.(`tarefa:${focus[0].id}`) : onOpenTab?.("tarefas")
                }
                style={styles.metric}
              >
                <Text style={styles.metricLabel}>FOCO</Text>
                {focus[0] ? (
                  <>
                    <Text style={styles.metricFocus} numberOfLines={2}>{focus[0].name}</Text>
                    <Text style={[styles.metricFocusMeta, { color: areaColor(focus[0].area) }]}>
                      {focus[0].area} · {focus[0].due ?? focus[0].status}
                    </Text>
                  </>
                ) : (
                  <>
                    <Text style={styles.metricValue}>—</Text>
                    <Text style={styles.metricHint}>nada no radar</Text>
                  </>
                )}
              </Pressable>
              <Pressable onPress={() => onOpenTab?.("tarefas")} style={styles.metric}>
                <Text style={styles.metricLabel}>COBRANÇAS</Text>
                <Text style={styles.metricValue}>{loaded.has("digest") ? digest?.count ?? 0 : "—"}</Text>
                <Text style={styles.metricHint}>no radar</Text>
              </Pressable>
            </View>

            {/* Sem seção "Foco de hoje": na C a fila de execução sai da Home e o
                foco vira o stat FOCO acima (ordem aprovada: saudação → saldo →
                herói → stats → agenda → em espera → dock). */}
            <View style={styles.section}>
              <SectionHeader eyebrow="tempo" title="Agenda curta" action="abrir agenda" onAction={() => onOpenTab?.("abertura")} />
              <View style={styles.agendaCard}>
                {nextAgenda.length ? nextAgenda.map((item, index) => (
                  <View key={`${item.time}-${item.title}-${index}`} style={[styles.agendaRow, index > 0 && styles.agendaBorder]}>
                    {/* 08=C: bolinha sálvia na mesma linha, só na próxima. */}
                    <View style={[styles.agendaDot, index === 0 && { backgroundColor: colors.success }]} />
                    <Text style={styles.agendaTime}>{item.time}</Text>
                    <Text style={[styles.agendaTitle, index > 0 && styles.agendaTitleLater]} numberOfLines={1}>{item.title}</Text>
                    <Text style={styles.agendaSource}>{item.source}</Text>
                  </View>
                )) : loaded.has("abertura") ? (
                  <View style={styles.agendaRow}>
                    <View style={styles.agendaDot} />
                    <Text style={styles.agendaTime}>—</Text>
                    <Text style={styles.agendaEmpty}>nenhum horário confirmado</Text>
                  </View>
                ) : (
                  <View style={styles.agendaRow}>
                    <View style={styles.agendaDot} />
                    <Text style={styles.agendaTime}>—</Text>
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
                  {(signals.anki ?? 0) > 0 ? <Pressable onPress={() => onOpenTab?.("revisao")}><Badge label="anki" value={signals.anki ?? undefined} color={colors.lilac} /></Pressable> : null}
                  {(signals.reading ?? 0) > 0 ? <Pressable onPress={() => onOpenTab?.("leitura")}><Badge label="leituras" value={signals.reading ?? undefined} color={colors.primary} /></Pressable> : null}
                </View>
              </View>
            ) : null}
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
  content: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: 128 },
  topline: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  hairline: { height: 1, marginHorizontal: 2, marginBottom: spacing.lg },
  date: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, textTransform: "uppercase", letterSpacing: 1.2 },
  greeting: { fontFamily: fonts.display, fontSize: 30, color: colors.text, letterSpacing: -0.35, marginTop: 4 },
  name: { color: colors.primary },
  // Selo neutro (03=B): moldura line-strong, sem preenchimento nem bronze.
  levelSeal: { borderRadius: 13, borderWidth: 1, borderColor: "rgba(235,222,202,0.20)", paddingVertical: 7, paddingHorizontal: 12, alignItems: "center", justifyContent: "center" },
  levelSmall: { fontFamily: fonts.mono, fontSize: 7, color: colors.textMuted, letterSpacing: 1.4 },
  levelNumber: { fontFamily: fonts.display, fontSize: 18, color: colors.text, lineHeight: 20 },
  partial: { flexDirection: "row", alignItems: "center", gap: 7, marginBottom: spacing.md },
  partialText: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 11.5 },
  // Vindos da 1A: o indicador de parâmetros (linha 177) usa os dois, e o JSX
  // sobreviveu ao merge — perder estes estilos renderiza style={undefined}.
  paramsAviso: { flexDirection: "row", alignItems: "center", gap: 7, marginBottom: spacing.md },
  paramsAvisoText: { fontFamily: fonts.mono, color: colors.textMuted, fontSize: 10.5 },
  // hero/heroIcon ficam na versão da marca (moldura neutra, ícone 36 em 14):
  // é restilização deliberada, mais nova que a da 1A.
  hero: { minHeight: 188, borderRadius: radius.xl, padding: spacing.lg, borderWidth: 1, borderColor: "rgba(235,222,202,0.20)", overflow: "hidden" },
  heroIcon: { position: "absolute", top: 14, right: 14, width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(222,184,120,0.1)", borderWidth: 1, borderColor: "rgba(222,184,120,0.18)" },
  heroEyebrow: { fontFamily: fonts.mono, fontSize: 10, color: colors.primary, letterSpacing: 1.6, textTransform: "uppercase" },
  heroTitle: { fontFamily: fonts.display, fontSize: 27, lineHeight: 31, color: colors.text, letterSpacing: -0.3, marginTop: spacing.lg, maxWidth: "82%" },
  heroSubtitle: { fontFamily: fonts.ui, fontSize: 13.5, lineHeight: 19, color: colors.textMuted, marginTop: 6, maxWidth: "88%" },
  heroFoot: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: "auto" },
  // O único bronze cheio da Home (05=C): pill bronze com fio de 2px na base.
  heroCta: { flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: colors.primary, borderBottomWidth: 2, borderBottomColor: "#B6935C", borderRadius: 9, paddingVertical: 9, paddingHorizontal: 14 },
  heroCtaText: { fontFamily: fonts.uiSemi, fontSize: 12, color: colors.primaryText },
  heroValue: { fontFamily: fonts.mono, fontSize: 10, color: colors.faint },
  metricsRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  metric: { flex: 1, minHeight: 92, borderRadius: radius.lg, padding: spacing.md, backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border },
  metricLabel: { fontFamily: fonts.mono, fontSize: 8.5, letterSpacing: 1.1, color: colors.textMuted },
  metricValue: { fontFamily: fonts.display, fontSize: 21, color: colors.text, marginTop: 8, marginBottom: 8 },
  metricMuted: { color: colors.textMuted, fontSize: 13 },
  metricHint: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 10.5 },
  // Coluna FOCO: nome de tarefa é uiSemi ~13px, NUNCA metricValue (display 21px
  // é tamanho de número-herói — o erro que a onda 2 evitou). O rodapé é mono
  // miúdo na cor da área, caixa alta.
  metricFocus: { fontFamily: fonts.uiSemi, fontSize: 13, lineHeight: 17, color: colors.text, marginTop: 8, marginBottom: 8 },
  metricFocusMeta: { fontFamily: fonts.mono, fontSize: 8.5, letterSpacing: 1, textTransform: "uppercase" },
  section: { marginTop: spacing.xl },
  agendaCard: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, paddingHorizontal: spacing.md },
  agendaRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10 },
  agendaBorder: { borderTopWidth: 1, borderTopColor: colors.border },
  agendaDot: { width: 5, height: 5, borderRadius: 3 },
  agendaTime: { width: 38, fontFamily: fonts.mono, fontSize: 11, color: colors.primary },
  agendaTitle: { flex: 1, fontFamily: fonts.uiSemi, fontSize: 13.5, color: colors.text },
  agendaTitleLater: { fontFamily: fonts.uiMedium },
  agendaSource: { fontFamily: fonts.mono, fontSize: 8.5, color: colors.faint, textTransform: "uppercase" },
  agendaEmpty: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  saldoCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
  },
  saldoRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  saldo: { fontFamily: fonts.mono, fontSize: 15, color: colors.text },
  saldoPts: { fontFamily: fonts.mono, fontSize: 9, color: colors.faint, letterSpacing: 0.8 },
  saldoCiclo: { fontFamily: fonts.mono, fontSize: 9, color: colors.faint, letterSpacing: 0.8 },
  captureDock: { position: "absolute", left: spacing.lg, right: spacing.lg, bottom: spacing.md, minHeight: 62, flexDirection: "row", alignItems: "center", gap: 11, backgroundColor: "#191D22", borderWidth: 1, borderColor: "rgba(222,184,120,0.23)", borderRadius: radius.xl, padding: 9, paddingRight: spacing.lg },
  capturePlus: { width: 42, height: 42, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: colors.primary },
  captureLabel: { fontFamily: fonts.mono, color: colors.primary, fontSize: 9, letterSpacing: 1, textTransform: "uppercase" },
  captureHint: { fontFamily: fonts.ui, color: colors.text, fontSize: 12.5, marginTop: 2 },
});
