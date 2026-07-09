import { Feather } from "@expo/vector-icons";
import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Digest, getDigest } from "../api";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { Skeleton } from "../ui";

function greeting(): string {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return "Bom dia";
  if (h >= 12 && h < 18) return "Boa tarde";
  return "Boa noite";
}

export default function Home({ onOpenTab }: { onOpenTab?: (t: string) => void }) {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    getDigest()
      .then((d) => {
        setDigest(d);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const prioridades = (digest?.tasks ?? []).slice(0, 3);
  const vencendo = digest?.count ?? 0;

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.md }}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.brand}>escritório</Text>

        <Text style={styles.greet}>
          {greeting()}, <Text style={styles.greetName}>Leo</Text>.
        </Text>
        <Text style={styles.brief}>
          {vencendo > 0
            ? `Você tem ${vencendo} ${vencendo === 1 ? "cobrança" : "cobranças"} hoje. Uma de cada vez.`
            : "Nada vencendo. Use o dia pra construir — não só apagar incêndio."}
        </Text>

        <View style={styles.state}>
          <Text style={styles.stateLabel}>estado</Text>
          <Text style={[styles.stateVal, { color: colors.success }]}>energia baixa</Text>
          <Text style={styles.stateDot}>·</Text>
          <Text style={[styles.stateVal, { color: colors.primary }]}>clareza alta</Text>
        </View>

        <Text style={styles.sectionLabel}>{prioridades.length ? "cobranças de hoje" : "hoje"}</Text>

        {loading ? (
          <>
            <Skeleton height={74} />
            <Skeleton height={74} />
            <Skeleton height={74} />
          </>
        ) : error ? (
          <Pressable onPress={load} style={styles.errRow}>
            <Feather name="refresh-cw" size={14} color={colors.textMuted} />
            <Text style={styles.muted}>não consegui carregar — toque pra tentar</Text>
          </Pressable>
        ) : prioridades.length ? (
          prioridades.map((p) => (
            <Pressable
              key={p.id}
              onPress={() => onOpenTab?.("revisao")}
              style={[styles.prio, { borderLeftColor: areaColor(p.area), shadowColor: areaColor(p.area) }]}
            >
              <View style={[styles.adot, { backgroundColor: areaColor(p.area) }]} />
              <View style={{ flex: 1 }}>
                <Text style={[styles.area, { color: areaColor(p.area) }]}>{p.area?.toLowerCase()}</Text>
                <Text style={styles.prioTitle}>{p.name}</Text>
                <Text style={styles.prioAction}>
                  {p.due ?? ""}
                  {p.assignee ? ` · ${p.assignee}` : ""}
                </Text>
              </View>
            </Pressable>
          ))
        ) : (
          <View style={styles.calm}>
            <Feather name="sunrise" size={26} color={colors.primary} />
            <Text style={styles.calmText}>tudo em dia. respira.</Text>
          </View>
        )}

        <View style={styles.radar}>
          <Pressable
            style={[styles.chip, vencendo > 0 && { borderColor: "rgba(222,138,122,0.4)" }]}
            onPress={() => onOpenTab?.("revisao")}
          >
            <Text style={styles.chipText}>
              vencendo <Text style={styles.chipNum}>{vencendo}</Text>
            </Text>
          </Pressable>
          <Pressable style={[styles.chip, styles.chipMentor]} onPress={() => onOpenTab?.("chat")}>
            <Text style={styles.chipMentorText}>◆ falar com o mentor</Text>
          </Pressable>
          <Pressable style={styles.chip} onPress={() => onOpenTab?.("fechar")}>
            <Text style={styles.chipText}>◗ fechar o dia</Text>
          </Pressable>
        </View>
      </ScrollView>

      <Pressable style={styles.dock} onPress={() => onOpenTab?.("capturar")}>
        <Text style={styles.dockHint}>Fala ou digita…</Text>
        <View style={styles.mic}>
          <Feather name="mic" size={20} color={colors.primaryText} />
        </View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  brand: { fontFamily: fonts.uiSemi, fontSize: 14, color: colors.textMuted, marginBottom: spacing.md },
  greet: { fontFamily: fonts.serif, fontSize: 30, color: colors.text, lineHeight: 34, letterSpacing: -0.3 },
  greetName: { color: colors.primary },
  brief: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 14, marginTop: 8, lineHeight: 20 },
  state: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 7,
    marginTop: 14,
    backgroundColor: "rgba(255,255,255,0.03)",
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 11,
    paddingVertical: 6,
    borderRadius: radius.pill,
  },
  stateLabel: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted },
  stateVal: { fontFamily: fonts.mono, fontSize: 11 },
  stateDot: { color: colors.textMuted, fontSize: 11 },
  sectionLabel: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
    letterSpacing: 1.4,
    textTransform: "uppercase",
    marginTop: spacing.xl,
    marginBottom: spacing.md,
    marginLeft: 2,
  },
  prio: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    padding: spacing.md,
    marginBottom: spacing.sm,
    flexDirection: "row",
    gap: 11,
    alignItems: "flex-start",
    shadowOpacity: 0.18,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 2,
  },
  adot: { width: 8, height: 8, borderRadius: 9, marginTop: 6 },
  area: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1, textTransform: "uppercase" },
  prioTitle: { fontFamily: fonts.uiSemi, fontSize: 16, color: colors.text, marginTop: 3, letterSpacing: -0.2 },
  prioAction: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, marginTop: 3 },
  calm: {
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xl,
    backgroundColor: colors.card2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
  },
  calmText: { fontFamily: fonts.serif, fontSize: 17, color: colors.text },
  errRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: spacing.md },
  muted: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  radar: { flexDirection: "row", gap: 8, marginTop: spacing.md, flexWrap: "wrap" },
  chip: {
    backgroundColor: "rgba(255,255,255,0.03)",
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: radius.pill,
  },
  chipText: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted },
  chipNum: { color: colors.text, fontFamily: fonts.mono },
  chipMentor: { borderColor: "rgba(201,169,126,0.4)", backgroundColor: colors.primarySoft },
  chipMentorText: { fontFamily: fonts.mono, fontSize: 11, color: colors.primary },
  dock: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.card2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    padding: 8,
    paddingLeft: 18,
  },
  dockHint: { flex: 1, fontFamily: fonts.ui, color: colors.textMuted, fontSize: 14 },
  mic: {
    width: 42,
    height: 42,
    borderRadius: 99,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
});
