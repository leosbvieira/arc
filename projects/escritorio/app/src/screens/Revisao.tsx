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

import { completeTask, Digest, getDigest, getPontos, Pontos, Task } from "../api";
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

// ---------------------------------------------------------------- Conquistas
// Lei nº4: 100% factual. O placar informa, não julga. Ganho em cor de sucesso;
// desconto em MUTED (nunca danger) — desconto não é erro, é fato. Sem streak-reset,
// sem elogio: se não houve padrão na semana, a seção some (não escrevemos "nenhum
// furo!", isso seria elogio).
const NIVEIS = [1, 2, 3, 4];

// 1553 -> "1.553" (sem depender de Intl no Hermes)
function num(n: number): string {
  return Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function Diamantes({ nivel }: { nivel: number }) {
  return (
    <View style={styles.diamonds}>
      {NIVEIS.map((n) => (
        <View key={n} style={[styles.diamond, n <= nivel && styles.diamondOn]} />
      ))}
    </View>
  );
}

function ConquistasCard({ p }: { p: Pontos }) {
  const { ciclo, semana, proximo_nivel } = p;
  const pct = ciclo.meta > 0 ? Math.max(0, Math.min(1, ciclo.pontos / ciclo.meta)) : 0;

  return (
    <Card style={styles.conqCard}>
      <View style={styles.conqHead}>
        <Text style={styles.conqLabel}>conquistas</Text>
        <Text style={styles.conqSaldo}>{num(p.saldo_total)} pts</Text>
      </View>

      <View style={styles.nivelRow}>
        <Text style={styles.nivel}>{p.nivel > 0 ? `N${p.nivel}` : "—"}</Text>
        <View style={{ flex: 1, gap: 4 }}>
          <Diamantes nivel={p.nivel} />
          <Text style={styles.vitalicio}>
            {p.nivel > 0 ? "vitalício · nível não regride" : "a caminho do N1"}
          </Text>
        </View>
      </View>

      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${pct * 100}%` }]} />
      </View>
      <View style={styles.cicloRow}>
        <Text style={styles.meta}>
          ciclo {ciclo.indice} · semana {ciclo.semana}/{ciclo.de}
        </Text>
        <Text style={styles.meta}>
          {num(ciclo.pontos)}/{num(ciclo.meta)}
        </Text>
      </View>

      <View style={styles.semanaRow}>
        <Text style={styles.semanaLabel}>semana</Text>
        <Text style={styles.ganho}>+{num(semana.ganho)}</Text>
        {semana.desconto > 0 ? (
          <Text style={styles.desconto}>−{num(semana.desconto)}</Text>
        ) : null}
      </View>

      {semana.padroes.length > 0 ? (
        <View style={styles.padroes}>
          {semana.padroes.map((pd) => (
            <Text key={pd.slug} style={styles.padrao}>
              {pd.nome} · {pd.furos} furos em 7d · −{num(pd.delta)}
            </Text>
          ))}
        </View>
      ) : null}

      <View style={styles.proximo}>
        <Text style={styles.meta}>
          {proximo_nivel
            ? `N${proximo_nivel.n} em ${num(proximo_nivel.faltam)} pts`
            : "N4 — topo"}
        </Text>
      </View>
    </Card>
  );
}

export default function Revisao() {
  const [d, setD] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  // Pontos tem estado PRÓPRIO: /pontos cair não pode derrubar a Revisão (o digest
  // continua). O painel degrada sozinho numa linha muda; o pull-to-refresh retenta.
  const [pontos, setPontos] = useState<Pontos | null>(null);
  const [pontosErr, setPontosErr] = useState(false);
  const [pontosLoading, setPontosLoading] = useState(true);

  const loadDigest = useCallback(async () => {
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

  const loadPontos = useCallback(async () => {
    setPontosLoading(true);
    try {
      setPontos(await getPontos());
      setPontosErr(false);
    } catch {
      setPontosErr(true);
    } finally {
      setPontosLoading(false);
    }
  }, []);

  const load = useCallback(async () => {
    await Promise.all([loadDigest(), loadPontos()]);
  }, [loadDigest, loadPontos]);

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

      <ScrollView
        style={{ marginTop: spacing.md }}
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      >
        {pontosLoading && !pontos ? (
          <Skeleton height={150} style={{ marginBottom: spacing.md }} />
        ) : pontos ? (
          <ConquistasCard p={pontos} />
        ) : pontosErr ? (
          <Card style={styles.conqOff}>
            <Text style={styles.conqOffText}>conquistas · sem dados agora</Text>
          </Card>
        ) : null}

        {loading ? (
          <View>
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
        ) : tasks.length > 0 ? (
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

  // ---- Conquistas ----
  conqCard: { marginBottom: spacing.md, gap: spacing.sm },
  conqHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  conqLabel: {
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: colors.textMuted,
  },
  conqSaldo: { fontFamily: fonts.mono, fontSize: 12, color: colors.textMuted },
  nivelRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  nivel: { fontFamily: fonts.serif, fontSize: 34, color: colors.text, lineHeight: 38 },
  diamonds: { flexDirection: "row", gap: 6 },
  diamond: {
    width: 9,
    height: 9,
    borderWidth: 1,
    borderColor: colors.textMuted,
    backgroundColor: "transparent",
    transform: [{ rotate: "45deg" }],
  },
  diamondOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  vitalicio: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  barTrack: {
    height: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.card2,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  barFill: { height: "100%", backgroundColor: colors.primary, borderRadius: radius.pill },
  cicloRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  semanaRow: { flexDirection: "row", alignItems: "baseline", gap: spacing.sm },
  semanaLabel: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, flex: 1 },
  ganho: { fontFamily: fonts.mono, fontSize: 15, color: colors.success },
  desconto: { fontFamily: fonts.mono, fontSize: 15, color: colors.textMuted },
  padroes: {
    gap: 3,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  padrao: { fontFamily: fonts.mono, fontSize: 11.5, color: colors.textMuted },
  proximo: { paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border },
  conqOff: { marginBottom: spacing.md, paddingVertical: spacing.md },
  conqOffText: { fontFamily: fonts.mono, fontSize: 11.5, color: colors.textMuted },

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
