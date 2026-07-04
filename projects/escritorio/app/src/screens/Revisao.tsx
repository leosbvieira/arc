import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { Digest, getDigest, Task } from "../api";
import { areaColor, colors, radius, spacing } from "../theme";
import { Card } from "../ui";

function severity(t: Task): { color: string; icon: string } {
  const d = (t.due ?? "").toLowerCase();
  if (d.startsWith("atrasada")) {
    const n = parseInt(d.replace(/\D+/g, "") || "0", 10);
    if (n >= 7) return { color: colors.danger, icon: "🚨" };
    if (n >= 3) return { color: colors.danger, icon: "🔴" };
    return { color: colors.amber, icon: "🟠" };
  }
  return { color: colors.amber, icon: "🟡" };
}

export default function Revisao() {
  const [d, setD] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setD(await getDigest());
    } catch (e: any) {
      Alert.alert("Revisão", e?.message ?? "falhou");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <ActivityIndicator style={{ marginTop: 24 }} />;
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

      <ScrollView
        style={{ marginTop: spacing.md }}
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      >
        {tasks.length > 0 ? (
          tasks.map((t) => {
            const s = severity(t);
            return (
              <View key={t.id} style={[styles.row, { borderLeftColor: s.color }]}>
                <Text style={{ fontSize: 18 }}>{s.icon}</Text>
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
              </View>
            );
          })
        ) : (
          <Card style={styles.emptyCard}>
            <Text style={{ fontSize: 32 }}>✅</Text>
            <Text style={{ color: colors.textMuted, marginTop: spacing.sm }}>tudo em dia</Text>
          </Card>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  title: { fontSize: 18, fontWeight: "700", color: colors.text },
  badge: {
    backgroundColor: colors.primary,
    borderRadius: radius.pill,
    minWidth: 26,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignItems: "center",
  },
  badgeText: { color: "#fff", fontWeight: "700", fontSize: 13 },
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
  name: { fontSize: 15.5, color: colors.text, fontWeight: "500" },
  meta: { fontSize: 12.5, color: colors.textMuted, marginTop: 3 },
  areaTag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.sm },
  areaTagText: { fontSize: 11, fontWeight: "700" },
  emptyCard: { alignItems: "center", paddingVertical: spacing.xl },
});
