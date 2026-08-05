import { Feather } from "@expo/vector-icons";
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { completeTask, createTask, listTasks, Task, TasksByArea } from "../api";
import { DueChoice, dueFromChoice, horaValida } from "../taskDue";
import { TaskDetailModal } from "../TaskDetailModal";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { AppButton, ErrorState, Field, SectionHeader, Skeleton } from "../ui";

const AREAS = [
  "Trabalho", "Staging", "Corpo", "Saúde Mental", "Responsabilidade",
  "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer",
];

type Bucket = "agora" | "proximas" | "programadas" | "backlog";

function bucket(task: Task): Bucket {
  if (task.days_overdue === null || task.days_overdue === undefined) return "backlog";
  if (task.days_overdue >= -7) return "agora";
  if (task.days_overdue >= -30) return "proximas";
  return "programadas";
}

function severityColor(task: Task): string {
  if (task.severity === "urgente" || task.severity === "firme") return colors.danger;
  if (task.days_overdue !== null && task.days_overdue !== undefined && task.days_overdue >= 0) return colors.danger;
  return areaColor(task.area);
}

function TaskRow({
  task,
  onOpen,
  onComplete,
}: {
  task: Task;
  onOpen: () => void;
  onComplete: () => void;
}) {
  const color = severityColor(task);
  return (
    <View style={styles.taskRow}>
      <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: false }} accessibilityLabel={`Concluir ${task.name}`} onPress={onComplete} hitSlop={5} style={[styles.check, { borderColor: `${color}AA` }]}>
        <View style={[styles.checkCore, { backgroundColor: `${color}20` }]} />
      </Pressable>
      <Pressable style={styles.taskBody} onPress={onOpen}>
        <View style={styles.taskTopline}>
          <Text style={[styles.taskArea, { color }]}>{task.area}</Text>
          {task.due ? <Text style={styles.taskDue}>{task.due}</Text> : null}
        </View>
        <Text style={styles.taskName} numberOfLines={2}>{task.name}</Text>
        {task.assignee ? <Text style={styles.assignee}>com {task.assignee}</Text> : null}
      </Pressable>
      <Pressable accessibilityLabel={`Abrir ${task.name}`} onPress={onOpen} hitSlop={8}>
        <Feather name="arrow-up-right" size={16} color={colors.textMuted} />
      </Pressable>
    </View>
  );
}

export default function Tasks({
  initialTaskId = null,
  onInitialTaskConsumed,
}: {
  initialTaskId?: string | null;
  onInitialTaskConsumed?: () => void;
}) {
  const [data, setData] = useState<TasksByArea | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);
  const [name, setName] = useState("");
  const [area, setArea] = useState("Staging");
  const [areaFilter, setAreaFilter] = useState("Todas");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [due, setDue] = useState<DueChoice>(null);
  const [hora, setHora] = useState("");
  const [scheduledOpen, setScheduledOpen] = useState(false);
  const [backlogOpen, setBacklogOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [pendingCompletion, setPendingCompletion] = useState<Task | null>(null);

  const load = useCallback(async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true);
    try {
      setData(await listTasks());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!initialTaskId) return;
    setDetailId(initialTaskId);
    onInitialTaskConsumed?.();
  }, [initialTaskId, onInitialTaskConsumed]);

  async function onCreate() {
    if (!name.trim() || busy) return;
    const horaLimpa = hora.trim();
    if (horaLimpa && !horaValida(horaLimpa)) {
      Alert.alert("Horário", "Use o formato HH:MM (ex.: 15:30).");
      return;
    }
    setBusy(true);
    let created = false;
    try {
      // Sem prazo a tarefa nunca é cobrada; com hora, o BFF também agenda o ⏰.
      const prazo = dueFromChoice(horaLimpa && due === null ? "hoje" : due);
      await createTask(name.trim(), area, prazo, horaLimpa || null);
      setName("");
      setDue(null);
      setHora("");
      setCreateOpen(false);
      created = true;
    } catch (error) {
      Alert.alert("Criar tarefa", error instanceof Error ? error.message : "Não foi possível criar.");
    } finally {
      setBusy(false);
    }
    if (created) await load(true);
  }

  async function completeById(id: string): Promise<boolean> {
    if (completingId) return false;
    setCompletingId(id);
    try {
      await completeTask(id);
    } catch (error) {
      Alert.alert("Concluir tarefa", error instanceof Error ? error.message : "Não foi possível concluir.");
      return false;
    } finally {
      setCompletingId(null);
    }
    await load(true);
    return true;
  }

  const allTasks = (data?.areas ?? []).flatMap((group) => group.tasks);
  const normalizedQuery = query.trim().toLocaleLowerCase("pt-BR");
  const filtered = allTasks.filter((task) => {
    const matchesArea = areaFilter === "Todas" || task.area === areaFilter;
    const matchesQuery = !normalizedQuery || `${task.name} ${task.area}`.toLocaleLowerCase("pt-BR").includes(normalizedQuery);
    return matchesArea && matchesQuery;
  });
  const grouped: Record<Bucket, Task[]> = { agora: [], proximas: [], programadas: [], backlog: [] };
  filtered.forEach((task) => grouped[bucket(task)].push(task));
  (Object.keys(grouped) as Bucket[]).forEach((key) => {
    grouped[key].sort((a, b) => (b.days_overdue ?? -100000) - (a.days_overdue ?? -100000));
  });
  const overdue = allTasks.filter((task) => (task.days_overdue ?? -1) >= 0).length;
  const nextSeven = allTasks.filter((task) => (task.days_overdue ?? -99) < 0 && (task.days_overdue ?? -99) >= -7).length;

  function renderRows(tasks: Task[]) {
    return tasks.map((task) => (
      <TaskRow
        key={task.id}
        task={task}
        onOpen={() => setDetailId(task.id)}
        onComplete={() => setPendingCompletion(task)}
      />
    ));
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={72}
    >
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.listContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={colors.primary} />}
      >
      <View style={styles.toolbar}>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>CENTRAL DE EXECUÇÃO</Text>
          <Text style={styles.summary}>{allTasks.length} abertas · {overdue} atrasadas</Text>
        </View>
        <Pressable onPress={() => setCreateOpen((value) => !value)} style={[styles.addButton, createOpen && styles.addButtonOpen]}>
          <Feather name={createOpen ? "x" : "plus"} size={20} color={createOpen ? colors.text : colors.primaryText} />
        </Pressable>
      </View>

      {createOpen ? (
        <View style={styles.createPanel}>
          <Text style={styles.createTitle}>Nova ação</Text>
          <Field autoFocus value={name} onChangeText={setName} placeholder="O que precisa acontecer?" returnKeyType="done" onSubmitEditing={onCreate} />
          <Text style={styles.fieldLabel}>DESTINO</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.areaRail}>
            {AREAS.map((item) => {
              const active = item === area;
              return (
                <Pressable key={item} onPress={() => setArea(item)} style={[styles.areaPill, active && { borderColor: areaColor(item), backgroundColor: `${areaColor(item)}20` }]}>
                  <View style={[styles.areaDot, { backgroundColor: areaColor(item) }]} />
                  <Text style={[styles.areaPillText, active && { color: colors.text }]}>{item}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          <Text style={styles.fieldLabel}>PRAZO</Text>
          <View style={styles.dueRow}>
            {([
              { key: null, label: "sem prazo" },
              { key: "hoje", label: "hoje" },
              { key: "amanha", label: "amanhã" },
              { key: "semana", label: "em 7 dias" },
            ] as { key: DueChoice; label: string }[]).map((option) => {
              const active = option.key === due;
              return (
                <Pressable
                  key={option.label}
                  onPress={() => setDue(option.key)}
                  style={[styles.duePill, active && styles.duePillActive]}
                >
                  <Text style={[styles.duePillText, active && styles.duePillTextActive]}>
                    {option.label}
                  </Text>
                </Pressable>
              );
            })}
            <Field
              style={styles.horaField}
              value={hora}
              onChangeText={setHora}
              placeholder="hh:mm"
              keyboardType="numbers-and-punctuation"
              maxLength={5}
            />
          </View>
          <Text style={styles.dueHint}>
            {due === null && !hora.trim()
              ? "Sem prazo, o sistema não cobra — fica só na lista."
              : hora.trim()
                ? "Com horário você recebe um aviso na hora marcada."
                : "Entra na cobrança do dia."}
          </Text>
          <AppButton title={area === "Staging" ? "Adicionar à triagem" : `Adicionar em ${area}`} onPress={onCreate} loading={busy} />
        </View>
      ) : null}

      <Field style={styles.search} value={query} onChangeText={setQuery} placeholder="Buscar tarefas" />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
        {["Todas", ...AREAS].map((item) => {
          const active = item === areaFilter;
          return (
            <Pressable key={item} onPress={() => setAreaFilter(item)} style={[styles.filter, active && styles.filterActive]}>
              <Text style={[styles.filterText, active && styles.filterTextActive]}>{item}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {pendingCompletion ? (
        <View style={styles.completionConfirm}>
          <View style={styles.completionIcon}><Feather name="check" size={15} color={colors.success} /></View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={styles.completionLabel}>CONCLUIR TAREFA?</Text>
            <Text style={styles.completionName} numberOfLines={1}>{pendingCompletion.name}</Text>
          </View>
          <Pressable accessibilityRole="button" onPress={() => setPendingCompletion(null)} hitSlop={8}>
            <Text style={styles.completionCancel}>cancelar</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={completingId === pendingCompletion.id}
            onPress={async () => {
              if (await completeById(pendingCompletion.id)) setPendingCompletion(null);
            }}
            style={styles.completionDo}
          >
            <Text style={styles.completionDoText}>{completingId === pendingCompletion.id ? "…" : "concluir"}</Text>
          </Pressable>
        </View>
      ) : null}

      {loading ? (
        <View style={{ marginTop: spacing.md }}><Skeleton height={76} /><Skeleton height={76} /><Skeleton height={76} /></View>
      ) : error ? (
        <ErrorState message="Não consegui carregar as tarefas." hint="Verifique o servidor e tente novamente." onRetry={() => load()} />
      ) : (
        <View>
          <View style={styles.signalRow}>
            <View style={styles.signal}><Text style={styles.signalNumber}>{overdue}</Text><Text style={styles.signalLabel}>atrasadas</Text></View>
            <View style={styles.signal}><Text style={styles.signalNumber}>{nextSeven}</Text><Text style={styles.signalLabel}>em 7 dias</Text></View>
            <View style={styles.signal}><Text style={styles.signalNumber}>{grouped.programadas.length}</Text><Text style={styles.signalLabel}>programadas</Text></View>
          </View>

          {grouped.agora.length ? (
            <View style={styles.group}>
              <SectionHeader eyebrow="execução" title="Agora" />
              {renderRows(grouped.agora)}
            </View>
          ) : null}
          {grouped.proximas.length ? (
            <View style={styles.group}>
              <SectionHeader eyebrow="radar" title="Próximos 30 dias" />
              {renderRows(grouped.proximas)}
            </View>
          ) : null}
          {grouped.programadas.length ? (
            <View style={styles.group}>
              <Pressable onPress={() => setScheduledOpen((value) => !value)} style={styles.scheduledHead}>
                <View>
                  <Text style={styles.scheduledKicker}>DEPOIS</Text>
                  <Text style={styles.scheduledTitle}>{grouped.programadas.length} programadas</Text>
                </View>
                <Feather name={scheduledOpen ? "chevron-up" : "chevron-down"} size={18} color={colors.textMuted} />
              </Pressable>
              {scheduledOpen || areaFilter !== "Todas" || normalizedQuery ? renderRows(grouped.programadas) : null}
            </View>
          ) : null}
          {grouped.backlog.length ? (
            <View style={styles.group}>
              <Pressable onPress={() => setBacklogOpen((value) => !value)} style={styles.scheduledHead}>
                <View>
                  <Text style={styles.scheduledKicker}>SEM PRAZO</Text>
                  <Text style={styles.scheduledTitle}>{grouped.backlog.length} no backlog</Text>
                </View>
                <Feather name={backlogOpen ? "chevron-up" : "chevron-down"} size={18} color={colors.textMuted} />
              </Pressable>
              {backlogOpen || areaFilter !== "Todas" || normalizedQuery ? renderRows(grouped.backlog) : null}
            </View>
          ) : null}
          {!filtered.length ? (
            <View style={styles.empty}><Feather name="check-circle" size={25} color={colors.success} /><Text style={styles.emptyTitle}>Nada nesta vista.</Text><Text style={styles.emptyText}>Troque o filtro ou capture uma nova ação.</Text></View>
          ) : null}
        </View>
      )}
      </ScrollView>

      <TaskDetailModal taskId={detailId} onClose={() => setDetailId(null)} onComplete={completeById} onAdiada={() => load(true)} />
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  toolbar: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginBottom: spacing.md },
  kicker: { fontFamily: fonts.mono, color: colors.primary, fontSize: 9, letterSpacing: 1.4 },
  summary: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 12.5, marginTop: 4 },
  addButton: { width: 44, height: 44, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: colors.primary },
  addButtonOpen: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  createPanel: { gap: spacing.md, backgroundColor: colors.card2, borderWidth: 1, borderColor: "rgba(222,184,120,0.23)", borderRadius: radius.xl, padding: spacing.lg, marginBottom: spacing.md },
  createTitle: { fontFamily: fonts.serif, fontSize: 20, color: colors.text },
  fieldLabel: { fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted, letterSpacing: 1.2 },
  dueRow: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.xs },
  duePill: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  duePillActive: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  duePillText: { fontFamily: fonts.ui, fontSize: 12, color: colors.textMuted },
  duePillTextActive: { color: colors.text, fontFamily: fonts.uiSemi },
  horaField: { width: 78 },
  dueHint: { fontFamily: fonts.ui, fontSize: 11, color: colors.textMuted, marginTop: -spacing.xs },
  areaRail: { gap: spacing.sm, paddingRight: spacing.lg },
  areaPill: { minHeight: 34, flexDirection: "row", alignItems: "center", gap: 7, borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 11 },
  areaDot: { width: 6, height: 6, borderRadius: 3 },
  areaPillText: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  search: { height: 44, backgroundColor: colors.card2 },
  filters: { gap: 7, paddingVertical: spacing.md, paddingRight: spacing.lg },
  filter: { minHeight: 32, justifyContent: "center", borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12 },
  filterActive: { backgroundColor: colors.primarySoft, borderColor: "rgba(222,184,120,0.35)" },
  filterText: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 11.5 },
  filterTextActive: { color: colors.primary, fontFamily: fonts.uiSemi },
  listContent: { paddingBottom: spacing.xxl },
  completionConfirm: { flexDirection: "row", alignItems: "center", gap: spacing.sm, minHeight: 62, marginBottom: spacing.md, padding: spacing.sm, borderWidth: 1, borderColor: "rgba(111,181,140,0.3)", borderRadius: radius.md, backgroundColor: "rgba(111,181,140,0.06)" },
  completionIcon: { width: 30, height: 30, borderRadius: 10, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(111,181,140,0.12)" },
  completionLabel: { fontFamily: fonts.mono, fontSize: 8.5, letterSpacing: 1, color: colors.success },
  completionName: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.text, marginTop: 2 },
  completionCancel: { fontFamily: fonts.ui, fontSize: 10.5, color: colors.textMuted },
  completionDo: { height: 34, justifyContent: "center", paddingHorizontal: 10, borderRadius: radius.sm, backgroundColor: colors.success },
  completionDoText: { fontFamily: fonts.uiSemi, fontSize: 10.5, color: colors.primaryText },
  signalRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.lg },
  signal: { flex: 1, backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md },
  signalNumber: { fontFamily: fonts.serif, color: colors.text, fontSize: 20 },
  signalLabel: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 9.5, marginTop: 2 },
  group: { marginBottom: spacing.xl },
  taskRow: { minHeight: 76, flexDirection: "row", alignItems: "center", gap: 11, borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: 10 },
  check: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center", borderWidth: 1.5 },
  checkCore: { width: 12, height: 12, borderRadius: 6 },
  taskBody: { flex: 1 },
  taskTopline: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  taskArea: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: 1, textTransform: "uppercase" },
  taskDue: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted },
  taskName: { fontFamily: fonts.uiSemi, fontSize: 14.5, lineHeight: 18.5, color: colors.text, marginTop: 4 },
  assignee: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 10.5, marginTop: 3 },
  scheduledHead: { minHeight: 70, flexDirection: "row", alignItems: "center", justifyContent: "space-between", backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, paddingHorizontal: spacing.lg },
  scheduledKicker: { fontFamily: fonts.mono, color: colors.textMuted, fontSize: 8.5, letterSpacing: 1.3 },
  scheduledTitle: { fontFamily: fonts.uiSemi, color: colors.text, fontSize: 13.5, marginTop: 3 },
  empty: { alignItems: "center", paddingVertical: spacing.xxl, gap: spacing.sm },
  emptyTitle: { fontFamily: fonts.serif, color: colors.text, fontSize: 18 },
  emptyText: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 12 },
});
