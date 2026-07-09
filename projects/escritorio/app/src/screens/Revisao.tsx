import { Feather } from "@expo/vector-icons";
import { ComponentProps, useCallback, useEffect, useState } from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { completeTask, Digest, getDigest, Task } from "../api";
import { TaskDetailModal } from "../TaskDetailModal";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { Card, ErrorState, Skeleton } from "../ui";

// Exibição pura: a severidade vem pronta do back (Task.severity). O front só mapeia
// nível -> cor/ícone; não parseia mais a string `due` (fonte única no BFF, P0.2).
type FeatherName = ComponentProps<typeof Feather>["name"];

const SEVERITY_STYLE: Record<string, { color: string; icon: FeatherName }> = {
  urgente: { color: colors.danger, icon: "alert-octagon" },
  firme: { color: colors.danger, icon: "alert-circle" },
  leve: { color: colors.amber, icon: "alert-triangle" },
  no_prazo: { color: colors.amber, icon: "clock" },
};

const styleFor = (t: Task) => SEVERITY_STYLE[t.severity ?? "no_prazo"];

export default function Revisao() {
  const [d, setD] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setD(await getDigest());
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

  async function completeById(id: string) {
    try {
      await completeTask(id);
      await load();
    } catch (e: any) {
      Alert.alert("Concluir", e?.message ?? "falhou");
    }
  }

  const tasks = d?.tasks ?? [];

  return (
    <View style={{ flex: 1, paddingTop: spacing.sm }}>
      <View style={styles.head}>
        <Text style={styles.title}>Cobranças de hoje</Text>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{d?.count ?? 0}</Text>
        </View>
      </View>

      {loading ? (
        <View style={{ marginTop: spacing.lg }}>
          <Skeleton height={64} />
          <Skeleton height={64} />
          <Skeleton height={64} />
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
        {tasks.length > 0 ? (
          tasks.map((t) => {
            const s = styleFor(t);
            return (
              <Pressable
                key={t.id}
                onPress={() => setDetailId(t.id)}
                style={[styles.row, { borderLeftColor: s.color }]}
              >
                <Feather name={s.icon} size={18} color={s.color} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{t.name}</Text>
                  <Text style={styles.meta}>
                    {t.due ?? t.last_done ?? ""}
                    {t.assignee ? ` · ${t.assignee}` : ""}
                  </Text>
                </View>
                <View style={[styles.areaTag, { backgroundColor: areaColor(t.area) + "22" }]}>
                  <Text style={[styles.areaTagText, { color: areaColor(t.area) }]}>{t.area}</Text>
                </View>
              </Pressable>
            );
          })
        ) : (
          <Card style={styles.emptyCard}>
            <Feather name="check-circle" size={32} color={colors.success} />
            <Text style={styles.emptyText}>tudo em dia</Text>
          </Card>
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
  head: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  title: { fontFamily: fonts.serif, fontSize: 21, color: colors.text },
  badge: {
    backgroundColor: colors.primary,
    borderRadius: radius.pill,
    minWidth: 26,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignItems: "center",
  },
  badgeText: { fontFamily: fonts.uiBold, color: colors.primaryText, fontSize: 13 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  name: { fontFamily: fonts.uiSemi, fontSize: 15.5, color: colors.text },
  meta: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, marginTop: 3 },
  areaTag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.sm },
  areaTagText: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 0.5, textTransform: "uppercase" },
  emptyCard: { alignItems: "center", paddingVertical: spacing.xl, gap: spacing.sm },
  emptyText: { fontFamily: fonts.ui, color: colors.textMuted },
});
