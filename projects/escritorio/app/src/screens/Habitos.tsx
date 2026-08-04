import { Feather } from "@expo/vector-icons";
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  createReductionHabit,
  deleteReductionHabit,
  getPontos,
  listReductionHabits,
  listReductionOccurrences,
  Pontos,
  recordReductionOccurrence,
  ReductionHabit,
  ReductionOccurrence,
  undoReductionOccurrence,
} from "../api";
import { colors, fonts, radius, spacing } from "../theme";
import * as SecureStore from "../storage";
import { AppButton, Card, ErrorState, Field, ProgressBar, Skeleton } from "../ui";

function localDate(): string {
  const date = new Date();
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

function clientKey(habitId: number): string {
  return `habit:${habitId}:${Date.now()}:${Math.random().toString(36).slice(2, 9)}`;
}

const PENDING_OCCURRENCES_KEY = "reduction_occurrences_pending_v1";
type PendingOccurrence = { key: string; data: string };

async function pendingOccurrenceFor(habitId: number): Promise<PendingOccurrence> {
  const raw = await SecureStore.getItemAsync(PENDING_OCCURRENCES_KEY);
  let pending: Record<string, PendingOccurrence | string> = {};
  try { pending = raw ? JSON.parse(raw) as Record<string, PendingOccurrence | string> : {}; } catch { /* Recomeça só o mapa de retries. */ }
  const id = String(habitId);
  const saved = pending[id];
  const occurrence = typeof saved === "string"
    ? { key: saved, data: localDate() }
    : saved ?? { key: clientKey(habitId), data: localDate() };
  pending[id] = occurrence;
  await SecureStore.setItemAsync(PENDING_OCCURRENCES_KEY, JSON.stringify(pending));
  return occurrence;
}

async function clearPendingOccurrence(habitId: number): Promise<void> {
  const raw = await SecureStore.getItemAsync(PENDING_OCCURRENCES_KEY);
  if (!raw) return;
  let pending: Record<string, PendingOccurrence | string>;
  try { pending = JSON.parse(raw) as Record<string, PendingOccurrence | string>; } catch {
    await SecureStore.deleteItemAsync(PENDING_OCCURRENCES_KEY);
    return;
  }
  delete pending[String(habitId)];
  await SecureStore.setItemAsync(PENDING_OCCURRENCES_KEY, JSON.stringify(pending));
}

function eventTime(timestamp: number): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp * 1000));
}

function recentDates(days: number): Array<{ key: string; label: string }> {
  const formatter = new Intl.DateTimeFormat("pt-BR", { weekday: "narrow" });
  const dates: Array<{ key: string; label: string }> = [];
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const value = new Date();
    value.setHours(12, 0, 0, 0);
    value.setDate(value.getDate() - offset);
    const timezoneOffset = value.getTimezoneOffset() * 60_000;
    dates.push({
      key: new Date(value.getTime() - timezoneOffset).toISOString().slice(0, 10),
      label: formatter.format(value),
    });
  }
  return dates;
}

export default function Habitos() {
  const [habits, setHabits] = useState<ReductionHabit[]>([]);
  const [events, setEvents] = useState<ReductionOccurrence[]>([]);
  const [points, setPoints] = useState<Pontos | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState("");
  const [penalty, setPenalty] = useState(1);
  const [busy, setBusy] = useState<string | null>(null);
  const today = localDate();

  const load = useCallback(async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true);
    try {
      const [habitList, history, score] = await Promise.all([
        listReductionHabits(),
        listReductionOccurrences(),
        getPontos(),
      ]);
      setHabits(habitList);
      setEvents(history);
      setPoints(score);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createHabit() {
    const value = name.trim();
    if (!value || busy) return;
    setBusy("create");
    try {
      await createReductionHabit(value, penalty);
      setName("");
      setPenalty(1);
      setFormOpen(false);
      await load(true);
    } catch (cause) {
      Alert.alert("Novo acompanhamento", cause instanceof Error ? cause.message : "Não foi possível salvar.");
    } finally {
      setBusy(null);
    }
  }

  async function record(habit: ReductionHabit) {
    if (busy) return;
    setBusy(`habit:${habit.id}`);
    let recorded = false;
    try {
      const pending = await pendingOccurrenceFor(habit.id);
      await recordReductionOccurrence(habit.id, pending.key, pending.data);
      await clearPendingOccurrence(habit.id);
      recorded = true;
    } catch {
      Alert.alert(
        "Ocorrência ainda não confirmada",
        "Toque novamente para repetir a mesma operação com segurança.",
      );
    } finally {
      setBusy(null);
    }
    if (recorded) await load(true);
  }

  async function undo(event: ReductionOccurrence) {
    if (busy || event.desfeita) return;
    setBusy(`event:${event.id}`);
    try {
      await undoReductionOccurrence(event.id);
      await load(true);
    } catch (cause) {
      Alert.alert("Desfazer", cause instanceof Error ? cause.message : "Não foi possível desfazer.");
    } finally {
      setBusy(null);
    }
  }

  function archive(habit: ReductionHabit) {
    Alert.alert(
      "Pausar acompanhamento?",
      `“${habit.nome}” sai da lista. O histórico continua preservado.`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Pausar",
          onPress: async () => {
            setBusy(`archive:${habit.id}`);
            try {
              await deleteReductionHabit(habit.id);
              await load(true);
            } catch {
              Alert.alert("Pausar", "Não foi possível pausar agora.");
            } finally {
              setBusy(null);
            }
          },
        },
      ],
    );
  }

  if (loading) {
    return <View style={styles.loading}><Skeleton height={150} /><Skeleton height={96} /><Skeleton height={96} /></View>;
  }
  if (error) {
    return <ErrorState message="Não consegui carregar seus acompanhamentos." hint="O histórico não foi alterado." onRetry={() => load()} />;
  }

  const activeEvents = events.filter((event) => !event.desfeita);
  const routineAdjustment = (points?.semana.padroes ?? []).reduce(
    (total, pattern) => total + Math.max(0, -pattern.delta),
    0,
  );
  const thisWeekAdjustment = Math.max(
    0,
    (points?.semana.desconto ?? 0) - routineAdjustment,
  );
  const lastSevenDays = recentDates(7);

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={colors.primary} />}
    >
      <View style={styles.intro}>
        <View style={styles.introIcon}><Feather name="trending-down" size={21} color={colors.primary} /></View>
        <Text style={styles.eyebrow}>REDUZIR SEM ESCONDER</Text>
        <Text style={styles.title}>Consciência, não culpa.</Text>
        <Text style={styles.subtitle}>Registre o que aconteceu, veja o padrão e continue o dia. Seu histórico não é sua identidade.</Text>
      </View>

      <Card style={styles.scoreCard}>
        <View style={styles.scoreTop}>
          <View>
            <Text style={styles.scoreLabel}>AJUSTE DESTA SEMANA</Text>
            <Text style={styles.scoreValue}>{thisWeekAdjustment ? `-${thisWeekAdjustment}` : "0"}</Text>
          </View>
          <View style={styles.scoreSeal}><Feather name="shield" size={17} color={colors.success} /></View>
        </View>
        <ProgressBar value={points?.semana.teto_desconto ? thisWeekAdjustment / points.semana.teto_desconto : 0} color={colors.primary} />
        <Text style={styles.scoreHint}>O ajuste total é limitado. Para cada hábito, somente uma ocorrência por dia afeta os pontos.</Text>
      </Card>

      <View style={styles.sectionHead}>
        <View>
          <Text style={styles.eyebrow}>ACOMPANHAMENTOS</Text>
          <Text style={styles.sectionTitle}>O que você quer reduzir</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel="Novo acompanhamento" onPress={() => setFormOpen((value) => !value)} style={styles.addButton}>
          <Feather name={formOpen ? "x" : "plus"} size={19} color={colors.primaryText} />
        </Pressable>
      </View>

      {formOpen ? (
        <Card style={styles.form}>
          <Text style={styles.formTitle}>Novo acompanhamento</Text>
          <Field value={name} onChangeText={setName} placeholder="Ex.: rolar redes sem intenção" autoFocus />
          <Text style={styles.formLabel}>AJUSTE POR DIA</Text>
          <View style={styles.penalties}>
            {[1, 2, 3].map((value) => (
              <Pressable key={value} onPress={() => setPenalty(value)} style={[styles.penalty, penalty === value && styles.penaltyOn]}>
                <Text style={[styles.penaltyText, penalty === value && styles.penaltyTextOn]}>-{value}</Text>
              </Pressable>
            ))}
          </View>
          <Text style={styles.formHint}>Não use pontos para alimentação, medicação, sintomas ou saúde. Esses assuntos merecem registro neutro.</Text>
          <AppButton title="Começar acompanhamento" onPress={createHabit} loading={busy === "create"} disabled={!name.trim()} />
        </Card>
      ) : null}

      {habits.length === 0 ? (
        <View style={styles.empty}>
          <Feather name="compass" size={23} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>Nenhum acompanhamento ativo.</Text>
          <Text style={styles.emptyText}>Adicione somente algo que será útil observar, não uma lista de coisas para se cobrar.</Text>
        </View>
      ) : habits.map((habit) => {
        const todayEvents = activeEvents.filter((event) => event.habito_id === habit.id && event.data === today);
        const occurrenceDays = new Set(
          activeEvents
            .filter((event) => event.habito_id === habit.id)
            .map((event) => event.data),
        );
        const daysWithoutOccurrence = lastSevenDays.filter(
          (date) => !occurrenceDays.has(date.key),
        ).length;
        return (
          <View key={habit.id} style={styles.habitCard}>
            <View style={styles.habitTop}>
              <View style={{ flex: 1 }}>
                <Text style={styles.habitName}>{habit.nome}</Text>
                <Text style={styles.habitMeta}>{todayEvents.length ? `${todayEvents.length} ocorrência(s) hoje` : "nenhuma ocorrência hoje"}</Text>
              </View>
              <Pressable accessibilityLabel={`Pausar ${habit.nome}`} onPress={() => archive(habit)} hitSlop={10}>
                <Feather name="more-horizontal" size={18} color={colors.textMuted} />
              </Pressable>
            </View>
            <View style={styles.weekSummary}>
              <Text style={styles.weekSummaryText}>{daysWithoutOccurrence} de 7 dias sem ocorrência</Text>
              <View style={styles.weekStrip}>
                {lastSevenDays.map((date) => {
                  const occurred = occurrenceDays.has(date.key);
                  return (
                    <View
                      key={date.key}
                      accessible
                      accessibilityLabel={`${date.label}: ${occurred ? "com ocorrência" : "sem ocorrência"}`}
                      style={styles.weekDay}
                    >
                      <Text style={styles.weekDayLabel}>{date.label}</Text>
                      <View style={[styles.weekDot, occurred && styles.weekDotOccurred]} />
                    </View>
                  );
                })}
              </View>
            </View>
            <Pressable
              accessibilityRole="button"
              onPress={() => record(habit)}
              disabled={!!busy}
              style={({ pressed }) => [styles.recordButton, pressed && { opacity: 0.75 }]}
            >
              <View style={styles.recordIcon}><Feather name="plus" size={16} color={colors.primary} /></View>
              <Text style={styles.recordText}>Registrar ocorrência</Text>
              <Text style={styles.recordPenalty}>até -{habit.penalidade}/dia</Text>
            </Pressable>
          </View>
        );
      })}

      {events.length > 0 ? (
        <View style={styles.history}>
          <Text style={styles.eyebrow}>HISTÓRICO RECENTE</Text>
          {events.slice(0, 12).map((event) => (
            <View key={event.id} style={[styles.eventRow, event.desfeita && { opacity: 0.45 }]}>
              <View style={[styles.eventDot, { backgroundColor: event.desfeita ? colors.textMuted : event.penalizavel ? colors.primary : colors.info }]} />
              <View style={{ flex: 1 }}>
                <Text style={styles.eventName}>{event.nome}</Text>
                <Text style={styles.eventMeta}>{eventTime(event.registrada_em)} · {event.desfeita ? "desfeita" : event.penalizavel ? "primeira ocorrência do dia" : "ocorrência adicional no dia"}</Text>
              </View>
              {!event.desfeita ? (
                <Pressable accessibilityRole="button" accessibilityLabel={`Desfazer ${event.nome}`} onPress={() => undo(event)} hitSlop={8}>
                  <Text style={styles.undo}>desfazer</Text>
                </Pressable>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  loading: { gap: spacing.md, paddingTop: spacing.md },
  content: { paddingTop: spacing.xs, paddingBottom: spacing.xxxl, gap: spacing.md },
  intro: { padding: spacing.lg, gap: 7, borderWidth: 1, borderColor: "rgba(222,184,120,0.22)", borderRadius: radius.xl, backgroundColor: colors.card2 },
  introIcon: { width: 44, height: 44, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: colors.primarySoft, marginBottom: spacing.sm },
  eyebrow: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: 1.4, color: colors.primary },
  title: { fontFamily: fonts.serif, fontSize: 27, color: colors.text, letterSpacing: -0.6 },
  subtitle: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textMuted },
  scoreCard: { gap: spacing.md },
  scoreTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  scoreLabel: { fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted, letterSpacing: 1.2 },
  scoreValue: { fontFamily: fonts.serif, fontSize: 28, color: colors.text, marginTop: 3 },
  scoreSeal: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(111,181,140,0.1)" },
  scoreHint: { fontFamily: fonts.ui, fontSize: 11.5, lineHeight: 17, color: colors.textMuted },
  sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.sm },
  sectionTitle: { fontFamily: fonts.serif, fontSize: 20, color: colors.text, marginTop: 3 },
  addButton: { width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: colors.primary },
  form: { gap: spacing.md },
  formTitle: { fontFamily: fonts.serif, fontSize: 19, color: colors.text },
  formLabel: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: 1.2, color: colors.textMuted },
  penalties: { flexDirection: "row", gap: spacing.sm },
  penalty: { width: 52, height: 38, alignItems: "center", justifyContent: "center", borderRadius: radius.md, borderWidth: 1, borderColor: colors.border },
  penaltyOn: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  penaltyText: { fontFamily: fonts.mono, fontSize: 12, color: colors.textMuted },
  penaltyTextOn: { color: colors.primary },
  formHint: { fontFamily: fonts.ui, fontSize: 11, lineHeight: 16, color: colors.textMuted },
  habitCard: { gap: spacing.md, padding: spacing.lg, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, backgroundColor: colors.card },
  habitTop: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  habitName: { fontFamily: fonts.uiSemi, fontSize: 15, lineHeight: 20, color: colors.text },
  habitMeta: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted, marginTop: 3 },
  weekSummary: { gap: spacing.sm, paddingVertical: spacing.xs, borderTopWidth: 1, borderTopColor: colors.border },
  weekSummaryText: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  weekStrip: { flexDirection: "row", justifyContent: "space-between", maxWidth: 250 },
  weekDay: { alignItems: "center", gap: 5 },
  weekDayLabel: { fontFamily: fonts.mono, fontSize: 8.5, color: colors.textMuted, textTransform: "uppercase" },
  weekDot: { width: 9, height: 9, borderRadius: 5, backgroundColor: "rgba(111,181,140,0.65)" },
  weekDotOccurred: { backgroundColor: colors.primary },
  recordButton: { flexDirection: "row", alignItems: "center", gap: spacing.sm, minHeight: 46, paddingHorizontal: spacing.sm, borderRadius: radius.md, backgroundColor: colors.primarySoft },
  recordIcon: { width: 29, height: 29, borderRadius: 10, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(222,184,120,0.12)" },
  recordText: { flex: 1, fontFamily: fonts.uiSemi, fontSize: 12.5, color: colors.primary },
  recordPenalty: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted },
  empty: { alignItems: "center", padding: spacing.xl, gap: spacing.sm, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg },
  emptyTitle: { fontFamily: fonts.serif, fontSize: 17, color: colors.text },
  emptyText: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 18, color: colors.textMuted, textAlign: "center" },
  history: { gap: spacing.sm, marginTop: spacing.lg },
  eventRow: { minHeight: 58, flexDirection: "row", alignItems: "center", gap: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  eventDot: { width: 7, height: 7, borderRadius: 4 },
  eventName: { fontFamily: fonts.uiSemi, fontSize: 13, color: colors.text },
  eventMeta: { fontFamily: fonts.ui, fontSize: 10.5, color: colors.textMuted, marginTop: 3 },
  undo: { fontFamily: fonts.uiSemi, fontSize: 11, color: colors.primary },
});
