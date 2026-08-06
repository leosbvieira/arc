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
  ALVOS_MELHORIA,
  AlvoMelhoria,
  Melhoria,
  createMelhoria,
  escolherMelhoria,
  listMelhorias,
  setMelhoriaAlvo,
  setMelhoriaStatus,
} from "../api";
import { agruparMelhorias } from "../melhoriasView";
import { colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, ErrorState, Field, Skeleton } from "../ui";

const ALVO_LABEL: Record<AlvoMelhoria, string> = {
  app: "app",
  empresa: "empresa",
  fluxo: "fluxo",
};

const ALVO_HINT: Record<AlvoMelhoria, string> = {
  app: "sai numa sessão de programação",
  empresa: "sistema ou ferramenta da empresa",
  fluxo: "processo, hábito, jeito de fazer",
};

type AcaoMelhoria = (id: number, acao: () => Promise<unknown>) => void;

// Fora do corpo de Melhorias() de propósito: definido lá dentro, o React via um
// TIPO novo a cada render e desmontava/remontava todos os cards — e o campo de
// nova melhoria mora no mesmo ScrollView, então cada tecla digitada remontava a
// lista inteira.
function Item({
  item,
  destaque,
  ocupado,
  comBusy,
}: {
  item: Melhoria;
  destaque?: boolean;
  ocupado: boolean;
  comBusy: AcaoMelhoria;
}) {
  return (
    <Card style={[styles.itemCard, destaque && styles.destaqueCard, ocupado && styles.cardOcupado]}>
      <View style={styles.itemHead}>
        <Text style={[styles.alvoTag, destaque && styles.alvoTagDestaque]}>
          {item.alvo ? ALVO_LABEL[item.alvo] : "sem alvo"}
          {item.escolhida_semana ? ` · semana ${item.escolhida_semana}` : ""}
        </Text>
        {item.sensivel ? <Feather name="lock" size={12} color={colors.textMuted} /> : null}
      </View>
      <Text style={styles.itemTexto}>{item.texto}</Text>
      <View style={styles.actions}>
        {item.status === "novo" ? (
          <Pressable
            style={styles.primaryAction}
            disabled={ocupado}
            onPress={() => comBusy(item.id, () => escolherMelhoria(item.id))}
          >
            <Feather name="target" size={13} color={colors.primaryText} />
            <Text style={styles.primaryActionText}>fazer esta semana</Text>
          </Pressable>
        ) : null}
        {item.status === "escolhida" ? (
          <Pressable
            style={styles.action}
            disabled={ocupado}
            onPress={() => comBusy(item.id, () => setMelhoriaStatus(item.id, "novo"))}
          >
            <Text style={styles.actionText}>devolver à fila</Text>
          </Pressable>
        ) : null}
        <Pressable
          style={styles.action}
          disabled={ocupado}
          onPress={() => comBusy(item.id, () => setMelhoriaStatus(item.id, "feita"))}
        >
          <Text style={styles.actionText}>feita</Text>
        </Pressable>
        <Pressable
          style={styles.action}
          disabled={ocupado}
          onPress={() => comBusy(item.id, () => setMelhoriaStatus(item.id, "descartada"))}
        >
          <Text style={styles.actionMuted}>descartar</Text>
        </Pressable>
      </View>
      {/* Triar era porta de uma via: um toque errado mandava a melhoria pro balde
          `app`, que o review não cobra, e nenhum controle daqui trocava de volta —
          nem "descartar → voltar à fila", que não mexe no alvo. */}
      <View style={styles.chips}>
        {ALVOS_MELHORIA.filter((alvo) => alvo !== item.alvo).map((alvo) => (
          <Pressable
            key={alvo}
            style={styles.chipDiscreto}
            disabled={ocupado}
            onPress={() => comBusy(item.id, () => setMelhoriaAlvo(item.id, alvo))}
          >
            <Text style={styles.chipMuted}>→ {ALVO_LABEL[alvo]}</Text>
          </Pressable>
        ))}
      </View>
    </Card>
  );
}

export default function Melhorias() {
  const [itens, setItens] = useState<Melhoria[]>([]);
  const [semana, setSemana] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [texto, setTexto] = useState("");
  const [alvoNovo, setAlvoNovo] = useState<AlvoMelhoria | null>(null);
  const [sensivel, setSensivel] = useState(false);
  const [busy, setBusy] = useState<number | "novo" | null>(null);
  const [verResolvidas, setVerResolvidas] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resposta = await listMelhorias();
      setItens(resposta.melhorias);
      setSemana(resposta.semana);
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

  const comBusy = useCallback(
    async (id: number | "novo", acao: () => Promise<unknown>) => {
      setBusy(id);
      try {
        await acao();
        await load();
      } catch (e: any) {
        Alert.alert("Melhorias", e?.message ?? "não consegui atualizar");
      } finally {
        setBusy(null);
      }
    },
    [load],
  );

  async function adicionar() {
    const valor = texto.trim();
    if (!valor) return;
    await comBusy("novo", async () => {
      await createMelhoria(valor, alvoNovo, sensivel);
      setTexto("");
      setAlvoNovo(null);
      setSensivel(false);
    });
  }

  if (loading && itens.length === 0) {
    return (
      <View style={{ paddingTop: spacing.sm }}>
        <Skeleton height={175} />
        <Skeleton height={100} />
        <Skeleton height={100} />
      </View>
    );
  }

  if (error && itens.length === 0) {
    return (
      <ErrorState
        message="Não consegui carregar as melhorias."
        hint="Toque para tentar de novo."
        onRetry={load}
      />
    );
  }

  const grupos = agruparMelhorias(itens, semana);

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingTop: spacing.sm, paddingBottom: spacing.xxl }}
      refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.lead}>
        Melhoria não tem prazo, tem momento. Nada aqui vira tarefa nem cobra atraso.
      </Text>

      <Card style={styles.novoCard}>
        <Text style={styles.label}>NOVA MELHORIA</Text>
        <Field
          value={texto}
          onChangeText={setTexto}
          placeholder="o que dava pra ser melhor?"
          multiline
          style={{ minHeight: 82, textAlignVertical: "top" }}
        />
        <View style={styles.chips}>
          {ALVOS_MELHORIA.map((alvo) => {
            const ativo = alvoNovo === alvo;
            return (
              <Pressable
                key={alvo}
                style={[styles.chip, ativo && styles.chipAtivo]}
                onPress={() => setAlvoNovo(ativo ? null : alvo)}
              >
                <Text style={[styles.chipText, ativo && styles.chipTextAtivo]}>
                  {ALVO_LABEL[alvo]}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.hint}>
          {alvoNovo ? ALVO_HINT[alvoNovo] : "pode deixar sem alvo — você decide depois"}
        </Text>
        <Pressable style={styles.sensivelRow} onPress={() => setSensivel((v) => !v)}>
          <Feather
            name={sensivel ? "check-square" : "square"}
            size={16}
            color={sensivel ? colors.primary : colors.textMuted}
          />
          <Text style={styles.sensivelText}>conteúdo sensível</Text>
        </Pressable>
        <AppButton
          title="Guardar melhoria"
          onPress={adicionar}
          loading={busy === "novo"}
          disabled={!texto.trim()}
        />
        <Text style={styles.hint}>
          na captura universal: comece com “melhoria:” ou “melhoria app:”
        </Text>
      </Card>

      {grupos.escolhida ? (
        <>
          <Text style={styles.sectionLabel}>
            {semana ? `desta semana · ${semana}` : "escolhida"}
          </Text>
          <Item
            item={grupos.escolhida}
            destaque
            ocupado={busy === grupos.escolhida.id}
            comBusy={comBusy}
          />
        </>
      ) : null}

      {/* Escolha de semana anterior não some nem vira "desta semana": vira a
          pergunta. Apagar seria o sistema decidindo por ele (lei 3), e manter no
          topo era a mentira que travava o convite do review por meses. */}
      {grupos.vencidas.length > 0 ? (
        <>
          <Text style={styles.sectionLabel}>escolhidas antes · fez?</Text>
          {grupos.vencidas.map((item) => (
            <Item key={item.id} item={item} ocupado={busy === item.id} comBusy={comBusy} />
          ))}
        </>
      ) : null}

      {grupos.aTriar.length > 0 ? (
        <>
          <Text style={styles.sectionLabel}>a triar · um toque</Text>
          {grupos.aTriar.map((item) => (
            <Card key={item.id} style={styles.itemCard}>
              <Text style={styles.itemTexto}>{item.texto}</Text>
              <View style={styles.chips}>
                {ALVOS_MELHORIA.map((alvo) => (
                  <Pressable
                    key={alvo}
                    style={styles.chip}
                    onPress={() => comBusy(item.id, () => setMelhoriaAlvo(item.id, alvo))}
                  >
                    <Text style={styles.chipText}>{ALVO_LABEL[alvo]}</Text>
                  </Pressable>
                ))}
                <Pressable
                  style={styles.chip}
                  onPress={() => comBusy(item.id, () => setMelhoriaStatus(item.id, "descartada"))}
                >
                  <Text style={styles.chipMuted}>descartar</Text>
                </Pressable>
              </View>
            </Card>
          ))}
        </>
      ) : null}

      {ALVOS_MELHORIA.map((alvo) =>
        grupos.porAlvo[alvo].length === 0 ? null : (
          <View key={alvo}>
            <Text style={styles.sectionLabel}>
              {ALVO_LABEL[alvo]} · {grupos.porAlvo[alvo].length}
            </Text>
            {alvo === "app" ? (
              <Text style={styles.grupoHint}>
                estas saem comigo numa sessão de programação — não entram na conta do review.
              </Text>
            ) : null}
            {grupos.porAlvo[alvo].map((item) => (
              <Item key={item.id} item={item} ocupado={busy === item.id} comBusy={comBusy} />
            ))}
          </View>
        ),
      )}

      {itens.length === 0 ? (
        <Card style={styles.emptyCard}>
          <Feather name="zap" size={25} color={colors.primary} />
          <Text style={styles.emptyText}>nenhuma melhoria registrada ainda.</Text>
        </Card>
      ) : null}

      {grupos.resolvidas.length > 0 ? (
        <>
          <Pressable onPress={() => setVerResolvidas((v) => !v)}>
            <Text style={styles.sectionLabel}>
              resolvidas · {grupos.resolvidas.length} {verResolvidas ? "▾" : "▸"}
            </Text>
          </Pressable>
          {verResolvidas
            ? grupos.resolvidas.map((item) => (
                <Card key={item.id} style={styles.resolvidaCard}>
                  <Text style={styles.alvoTag}>
                    {item.status === "feita" ? "feita" : "descartada"}
                    {item.alvo ? ` · ${ALVO_LABEL[item.alvo]}` : ""}
                  </Text>
                  <Text style={styles.resolvidaTexto}>{item.texto}</Text>
                  <View style={styles.actions}>
                    <Pressable
                      style={styles.action}
                      onPress={() => comBusy(item.id, () => setMelhoriaStatus(item.id, "novo"))}
                    >
                      <Text style={styles.actionText}>voltar à fila</Text>
                    </Pressable>
                  </View>
                </Card>
              ))
            : null}
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  lead: { fontFamily: fonts.serif, fontSize: 18, lineHeight: 25, color: colors.text, marginBottom: spacing.md },
  novoCard: { gap: spacing.sm },
  label: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, letterSpacing: 1.1 },
  hint: { fontFamily: fonts.ui, fontSize: 12, color: colors.textMuted },
  grupoHint: { fontFamily: fonts.ui, fontSize: 12, color: colors.textMuted, marginBottom: spacing.sm },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  chip: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 11, paddingVertical: 6 },
  chipAtivo: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  chipText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.text },
  chipTextAtivo: { color: colors.primary },
  chipMuted: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  sensivelRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xs },
  sensivelText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  sectionLabel: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, letterSpacing: 1.2, textTransform: "uppercase", marginTop: spacing.xl, marginBottom: spacing.md },
  emptyCard: { alignItems: "center", gap: spacing.sm, marginTop: spacing.xl },
  emptyText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  itemCard: { gap: spacing.sm, marginBottom: spacing.sm },
  destaqueCard: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  cardOcupado: { opacity: 0.55 },
  chipDiscreto: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 9, paddingVertical: 4 },
  itemHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  alvoTag: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, letterSpacing: 1, textTransform: "uppercase" },
  alvoTagDestaque: { color: colors.primary },
  itemTexto: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 21, color: colors.text },
  resolvidaCard: { gap: spacing.xs, marginBottom: spacing.sm, opacity: 0.7 },
  resolvidaTexto: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textMuted },
  meta: { fontFamily: fonts.mono, fontSize: 10, color: colors.textMuted },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.xs },
  acaoOcupada: { opacity: 0.5 },
  action: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 11, paddingVertical: 7 },
  actionText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.text },
  actionMuted: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  primaryAction: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.primary, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 7 },
  primaryActionText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.primaryText },
});
