import Feather from "@expo/vector-icons/Feather";
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
  AREAS_TRIAGEM,
  AreaTriagem,
  ItemTriagem,
  aplicarTriagem,
  getTriagem,
} from "../api";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { resumoDaTriagem } from "../triagemResultado";
import { AppButton, Card, ErrorState, Skeleton } from "../ui";

export default function Triagem() {
  const [itens, setItens] = useState<ItemTriagem[]>([]);
  const [escolhas, setEscolhas] = useState<Record<string, AreaTriagem | null>>({});
  const [aprovados, setAprovados] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [aplicando, setAplicando] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const pack = await getTriagem();
      setItens(pack.itens);
      setEscolhas(
        Object.fromEntries(pack.itens.map((item) => [item.id, item.area_proposta])) as Record<
          string,
          AreaTriagem | null
        >,
      );
      // Sugestão nunca equivale a aprovação: todo lote começa desmarcado.
      setAprovados({});
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

  function escolher(item: ItemTriagem, area: AreaTriagem) {
    setEscolhas((atual) => ({ ...atual, [item.id]: area }));
    setAprovados((atual) => ({ ...atual, [item.id]: true }));
  }

  function alternarAprovacao(item: ItemTriagem) {
    if (!escolhas[item.id]) return;
    setAprovados((atual) => ({ ...atual, [item.id]: !atual[item.id] }));
  }

  const movimentos = itens.flatMap((item) => {
    const area = escolhas[item.id];
    return aprovados[item.id] && area ? [{ task_id: item.id, area }] : [];
  });

  function confirmarLote() {
    if (movimentos.length === 0) return;
    Alert.alert(
      "Aplicar triagem",
      `${movimentos.length} tarefa(s) serão movidas. As demais ficam no Staging.`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Mover aprovadas",
          onPress: async () => {
            setAplicando(true);
            try {
              const resultados = await aplicarTriagem(movimentos);
              Alert.alert("Triagem concluída", resumoDaTriagem(resultados));
              await load();
            } catch (e: any) {
              Alert.alert("Triagem", e?.message ?? "não consegui aplicar o lote");
            } finally {
              setAplicando(false);
            }
          },
        },
      ],
    );
  }

  if (loading && itens.length === 0) {
    return (
      <View style={{ paddingTop: spacing.sm }}>
        <Skeleton height={150} />
        <Skeleton height={150} />
      </View>
    );
  }

  if (error && itens.length === 0) {
    return (
      <ErrorState
        message="Não consegui abrir o Staging."
        hint="O BFF ou o ClickUp pode estar indisponível."
        onRetry={load}
      />
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingTop: spacing.sm, paddingBottom: spacing.xl }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      >
        <Text style={styles.lead}>
          A IA propõe o destino. Você revisa cada item e só o lote marcado é movido.
        </Text>
        <View style={styles.summary}>
          <Text style={styles.summaryLabel}>STAGING</Text>
          <Text style={styles.summaryCount}>{itens.length}</Text>
          <Text style={styles.summaryDot}>·</Text>
          <Text style={styles.summaryApproved}>{movimentos.length} aprovadas</Text>
        </View>

        {itens.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Feather name="inbox" size={27} color={colors.success} />
            <Text style={styles.emptyTitle}>Staging vazio</Text>
            <Text style={styles.emptyText}>não há decisões pendentes agora.</Text>
          </Card>
        ) : (
          itens.map((item) => {
            const escolha = escolhas[item.id];
            const aprovado = !!aprovados[item.id];
            return (
              <Card key={item.id} style={[styles.itemCard, aprovado && styles.itemApproved]}>
                <Pressable style={styles.itemHead} onPress={() => alternarAprovacao(item)}>
                  <Feather
                    name={aprovado ? "check-square" : "square"}
                    size={18}
                    color={aprovado ? colors.primary : colors.textMuted}
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.itemName}>{item.name}</Text>
                    <Text style={styles.itemMeta}>
                      {item.id}{item.idade_d !== null ? ` · ${item.idade_d}d no Staging` : ""}
                    </Text>
                  </View>
                </Pressable>

                {item.area_proposta ? (
                  <Text style={styles.proposta}>
                    sugestão da IA · {item.area_proposta}
                  </Text>
                ) : (
                  <Text style={styles.semProposta}>sem sugestão · escolha manualmente</Text>
                )}

                <View style={styles.areas}>
                  {AREAS_TRIAGEM.map((area) => {
                    const on = escolha === area;
                    const cor = areaColor(area);
                    return (
                      <Pressable
                        key={area}
                        onPress={() => escolher(item, area)}
                        style={[
                          styles.areaPill,
                          on && { borderColor: cor, backgroundColor: `${cor}22` },
                        ]}
                      >
                        <Text style={[styles.areaText, on && { color: cor }]}>{area}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              </Card>
            );
          })
        )}
      </ScrollView>

      {itens.length > 0 ? (
        <View style={styles.footer}>
          <AppButton
            title={`Revisar e mover ${movimentos.length}`}
            onPress={confirmarLote}
            loading={aplicando}
            disabled={movimentos.length === 0}
          />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  lead: { fontFamily: fonts.ui, fontSize: 18, lineHeight: 25, color: colors.text, marginBottom: spacing.md },
  summary: { flexDirection: "row", alignItems: "baseline", gap: 7, marginBottom: spacing.md },
  summaryLabel: { fontFamily: fonts.mono, fontSize: 10, color: colors.textMuted, letterSpacing: 1.2 },
  summaryCount: { fontFamily: fonts.display, fontSize: 25, color: colors.text },
  summaryDot: { color: colors.textMuted },
  summaryApproved: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.primary },
  itemCard: { gap: spacing.sm, marginBottom: spacing.sm },
  itemApproved: { borderColor: colors.primary },
  itemHead: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  itemName: { fontFamily: fonts.uiSemi, fontSize: 15, lineHeight: 20, color: colors.text },
  itemMeta: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, marginTop: 3 },
  proposta: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.primary },
  semProposta: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted },
  areas: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  areaPill: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 6 },
  areaText: { fontFamily: fonts.ui, fontSize: 11, color: colors.textMuted },
  emptyCard: { alignItems: "center", gap: spacing.xs, paddingVertical: spacing.xl },
  emptyTitle: { fontFamily: fonts.uiSemi, fontSize: 18, color: colors.text },
  emptyText: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted },
  footer: { paddingTop: spacing.sm, paddingBottom: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg },
});
