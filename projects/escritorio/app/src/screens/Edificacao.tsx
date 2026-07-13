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
  Aprendizado,
  createAprendizado,
  listAprendizados,
  praticarAprendizado,
  setAprendizadoStatus,
} from "../api";
import { colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, ErrorState, Field, Skeleton } from "../ui";

const STATUS_LABEL: Record<string, string> = {
  novo: "novo",
  pratica: "prática da semana",
  aplicado: "aplicado",
  arquivado: "arquivado",
};

export default function Edificacao() {
  const [itens, setItens] = useState<Aprendizado[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [texto, setTexto] = useState("");
  const [sensivel, setSensivel] = useState(false);
  const [busy, setBusy] = useState<number | "novo" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItens(await listAprendizados());
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

  async function adicionar() {
    const valor = texto.trim();
    if (!valor) return;
    setBusy("novo");
    try {
      await createAprendizado(valor, sensivel);
      setTexto("");
      setSensivel(false);
      await load();
    } catch (e: any) {
      Alert.alert("Edificação", e?.message ?? "não consegui salvar");
    } finally {
      setBusy(null);
    }
  }

  function escolherPratica(item: Aprendizado) {
    Alert.alert(
      "Prática da semana",
      "Esta escolha substitui a prática atual. Continuar?",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Escolher",
          onPress: async () => {
            setBusy(item.id);
            try {
              await praticarAprendizado(item.id);
              await load();
            } catch (e: any) {
              Alert.alert("Edificação", e?.message ?? "não consegui escolher a prática");
            } finally {
              setBusy(null);
            }
          },
        },
      ],
    );
  }

  async function mudarStatus(item: Aprendizado, status: "novo" | "aplicado" | "arquivado") {
    setBusy(item.id);
    try {
      await setAprendizadoStatus(item.id, status);
      await load();
    } catch (e: any) {
      Alert.alert("Edificação", e?.message ?? "não consegui atualizar");
    } finally {
      setBusy(null);
    }
  }

  if (loading && itens.length === 0) {
    return (
      <View style={{ paddingTop: spacing.sm }}>
        <Skeleton height={155} />
        <Skeleton height={100} />
        <Skeleton height={100} />
      </View>
    );
  }

  if (error && itens.length === 0) {
    return (
      <ErrorState
        message="Não consegui carregar os aprendizados."
        hint="Toque para tentar de novo."
        onRetry={load}
      />
    );
  }

  const ordenados = [...itens].sort((a, b) => {
    if (a.status === "pratica") return -1;
    if (b.status === "pratica") return 1;
    return b.criado - a.criado;
  });

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingTop: spacing.sm, paddingBottom: spacing.xxl }}
      refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.lead}>
        Um aprendizado escolhido vira prática acompanhada. O resto continua como repertório.
      </Text>

      <Card style={styles.novoCard}>
        <Text style={styles.label}>NOVO APRENDIZADO</Text>
        <Field
          value={texto}
          onChangeText={setTexto}
          placeholder="o que vale lembrar e aplicar?"
          multiline
          style={{ minHeight: 82, textAlignVertical: "top" }}
        />
        <Pressable style={styles.sensivelRow} onPress={() => setSensivel((v) => !v)}>
          <Feather
            name={sensivel ? "check-square" : "square"}
            size={16}
            color={sensivel ? colors.primary : colors.textMuted}
          />
          <Text style={styles.sensivelText}>conteúdo sensível</Text>
        </Pressable>
        <AppButton
          title="Guardar aprendizado"
          onPress={adicionar}
          loading={busy === "novo"}
          disabled={!texto.trim()}
        />
      </Card>

      <Text style={styles.sectionLabel}>repertório</Text>
      {ordenados.length === 0 ? (
        <Card style={styles.emptyCard}>
          <Feather name="compass" size={25} color={colors.primary} />
          <Text style={styles.emptyText}>nenhum aprendizado registrado ainda.</Text>
        </Card>
      ) : (
        ordenados.map((item) => (
          <Card
            key={item.id}
            style={[styles.itemCard, item.status === "pratica" && styles.praticaCard]}
          >
            <View style={styles.itemHead}>
              <Text style={[styles.status, item.status === "pratica" && styles.statusPratica]}>
                {STATUS_LABEL[item.status] ?? item.status}
              </Text>
              {item.sensivel ? <Feather name="lock" size={12} color={colors.textMuted} /> : null}
            </View>
            <Text style={styles.itemTexto}>{item.texto}</Text>
            {item.pratica_semana ? (
              <Text style={styles.meta}>semana {item.pratica_semana}</Text>
            ) : null}
            <View style={styles.actions}>
              {item.status !== "pratica" && item.status !== "arquivado" ? (
                <Pressable style={styles.primaryAction} onPress={() => escolherPratica(item)}>
                  <Feather name="target" size={13} color={colors.primaryText} />
                  <Text style={styles.primaryActionText}>praticar</Text>
                </Pressable>
              ) : null}
              {item.status === "pratica" || item.status === "novo" ? (
                <Pressable style={styles.action} onPress={() => mudarStatus(item, "aplicado")}>
                  <Text style={styles.actionText}>marcar aplicado</Text>
                </Pressable>
              ) : null}
              {item.status === "aplicado" || item.status === "arquivado" ? (
                <Pressable style={styles.action} onPress={() => mudarStatus(item, "novo")}>
                  <Text style={styles.actionText}>voltar a novos</Text>
                </Pressable>
              ) : null}
              {item.status !== "arquivado" ? (
                <Pressable style={styles.action} onPress={() => mudarStatus(item, "arquivado")}>
                  <Text style={styles.actionMuted}>arquivar</Text>
                </Pressable>
              ) : null}
            </View>
          </Card>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  lead: { fontFamily: fonts.serif, fontSize: 18, lineHeight: 25, color: colors.text, marginBottom: spacing.md },
  novoCard: { gap: spacing.sm },
  label: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, letterSpacing: 1.1 },
  sensivelRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xs },
  sensivelText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  sectionLabel: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, letterSpacing: 1.2, textTransform: "uppercase", marginTop: spacing.xl, marginBottom: spacing.md },
  emptyCard: { alignItems: "center", gap: spacing.sm },
  emptyText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  itemCard: { gap: spacing.sm, marginBottom: spacing.sm },
  praticaCard: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  itemHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  status: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, letterSpacing: 1, textTransform: "uppercase" },
  statusPratica: { color: colors.primary },
  itemTexto: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 21, color: colors.text },
  meta: { fontFamily: fonts.mono, fontSize: 10, color: colors.textMuted },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.xs },
  action: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 11, paddingVertical: 7 },
  actionText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.text },
  actionMuted: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  primaryAction: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.primary, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 7 },
  primaryActionText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.primaryText },
});
