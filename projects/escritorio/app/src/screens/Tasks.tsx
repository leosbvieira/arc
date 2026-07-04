import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { completeTask, createTask, listTasks, Task, TasksByArea } from "../api";
import { areaColor, colors, radius, spacing } from "../theme";
import { AppButton, Card, Field } from "../ui";

const AREAS = ["Trabalho", "Finanças", "Saúde", "Pessoal"];

function meta(t: Task): string {
  if (t.due) return t.due;
  if (t.last_done) return `última vez ${t.last_done}`;
  return t.status;
}

export default function Tasks() {
  const [data, setData] = useState<TasksByArea | null>(null);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [area, setArea] = useState("Trabalho");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await listTasks());
    } catch (e: any) {
      Alert.alert("Tarefas", e?.message ?? "falhou");
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

  async function onDone(t: Task) {
    try {
      await completeTask(t.id);
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
        <ActivityIndicator style={{ marginTop: 24 }} />
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
                    <View style={{ flex: 1 }}>
                      <Text style={styles.taskName}>{t.name}</Text>
                      <Text style={styles.taskMeta}>
                        {meta(t)}
                        {t.assignee ? ` · ${t.assignee}` : ""}
                      </Text>
                    </View>
                    <Pressable onPress={() => onDone(t)} style={styles.check}>
                      <Text style={styles.checkText}>✓</Text>
                    </Pressable>
                  </View>
                ))}
              </View>
            ))
          ) : (
            <Text style={styles.empty}>tudo em dia ✅</Text>
          )}
        </ScrollView>
      )}
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
  pillText: { fontWeight: "600", fontSize: 13 },
  areaHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  dot: { width: 10, height: 10, borderRadius: 5 },
  areaLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
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
  taskName: { fontSize: 16, color: colors.text, fontWeight: "500" },
  taskMeta: { fontSize: 12.5, color: colors.textMuted, marginTop: 3 },
  check: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1.5,
    borderColor: colors.success,
    alignItems: "center",
    justifyContent: "center",
  },
  checkText: { color: colors.success, fontSize: 16, fontWeight: "700" },
  empty: { textAlign: "center", color: colors.textMuted, marginTop: 32 },
});
