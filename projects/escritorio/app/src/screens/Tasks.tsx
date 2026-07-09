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

import { completeTask, createTask, listTasks, Task, TasksByArea } from "../api";
import { TaskDetailModal } from "../TaskDetailModal";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, ErrorState, Field, Skeleton } from "../ui";

const AREAS = ["Trabalho", "Finanças", "Saúde", "Pessoal"];

function meta(t: Task): string {
  if (t.due) return t.due;
  if (t.last_done) return `última vez ${t.last_done}`;
  return t.status;
}

export default function Tasks() {
  const [data, setData] = useState<TasksByArea | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [name, setName] = useState("");
  const [area, setArea] = useState("Trabalho");
  const [busy, setBusy] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await listTasks());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function onCreate() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await createTask(name.trim(), area);
      setName("");
      await load();
    } catch (e: any) {
      Alert.alert("Criar", e?.message ?? "falhou");
    } finally {
      setBusy(false);
    }
  }

  async function completeById(id: string) {
    try {
      await completeTask(id);
      await load();
    } catch (e: any) {
      Alert.alert("Concluir", e?.message ?? "falhou");
    }
  }

  return (
    <View style={{ flex: 1 }}>
      <Card style={styles.newCard}>
        <Field value={name} onChangeText={setName} placeholder="nova tarefa" />
        <View style={styles.pills}>
          {AREAS.map((a) => {
            const on = a === area;
            return (
              <Pressable
                key={a}
                onPress={() => setArea(a)}
                style={[styles.pill, { borderColor: areaColor(a) }, on && { backgroundColor: areaColor(a) }]}
              >
                <Text style={[styles.pillText, { color: on ? "#fff" : areaColor(a) }]}>{a}</Text>
              </Pressable>
            );
          })}
        </View>
        <AppButton title="Adicionar" onPress={onCreate} loading={busy} />
      </Card>

      {loading ? (
        <View style={{ marginTop: spacing.lg }}>
          <Skeleton height={14} style={{ width: 84, marginLeft: 2 }} />
          <Skeleton height={70} />
          <Skeleton height={70} />
          <Skeleton height={14} style={{ width: 84, marginLeft: 2, marginTop: spacing.md }} />
          <Skeleton height={70} />
        </View>
      ) : error ? (
        <ErrorState
          message="Não consegui falar com o servidor."
          hint="O BFF (backend) está rodando na rede? Toque pra tentar de novo."
          onRetry={load}
        />
      ) : (
        <ScrollView
          style={{ marginTop: spacing.md }}
          contentContainerStyle={{ paddingBottom: spacing.xl }}
          refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        >
          {data && data.areas.length > 0 ? (
            data.areas.map((g) => (
              <View key={g.area} style={{ marginBottom: spacing.lg }}>
                <View style={styles.areaHead}>
                  <View style={[styles.dot, { backgroundColor: areaColor(g.area) }]} />
                  <Text style={styles.areaLabel}>{g.area}</Text>
                </View>
                {g.tasks.map((t) => (
                  <View key={t.id} style={[styles.taskCard, { borderLeftColor: areaColor(t.area) }]}>
                    <Pressable style={{ flex: 1 }} onPress={() => setDetailId(t.id)}>
                      <Text style={styles.taskName}>{t.name}</Text>
                      <Text style={styles.taskMeta}>
                        {meta(t)}
                        {t.assignee ? ` · ${t.assignee}` : ""}
                      </Text>
                    </Pressable>
                    <Feather name="chevron-right" size={16} color={colors.textMuted} />
                    <Pressable onPress={() => completeById(t.id)} style={styles.check} hitSlop={6}>
                      <Feather name="check" size={18} color={colors.success} />
                    </Pressable>
                  </View>
                ))}
              </View>
            ))
          ) : (
            <View style={styles.emptyWrap}>
              <Feather name="check-circle" size={30} color={colors.success} />
              <Text style={styles.empty}>tudo em dia</Text>
            </View>
          )}
        </ScrollView>
      )}

      <TaskDetailModal
        taskId={detailId}
        onClose={() => setDetailId(null)}
        onComplete={completeById}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  newCard: { gap: spacing.sm, marginTop: spacing.sm },
  pills: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  pill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1.5,
  },
  pillText: { fontFamily: fonts.uiSemi, fontSize: 13 },
  areaHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  dot: { width: 10, height: 10, borderRadius: 5 },
  areaLabel: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 1.2,
  },
  taskCard: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    padding: spacing.md,
    marginBottom: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  taskName: { fontFamily: fonts.uiSemi, fontSize: 15.5, color: colors.text },
  taskMeta: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, marginTop: 3 },
  check: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: colors.success,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyWrap: { alignItems: "center", marginTop: 40, gap: spacing.sm },
  empty: { fontFamily: fonts.ui, textAlign: "center", color: colors.textMuted },
});
