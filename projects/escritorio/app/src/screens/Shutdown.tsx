import Feather from "@expo/vector-icons/Feather";
import { useCallback, useEffect, useState } from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { Shutdown as ShutdownData, Task, completeTask, getShutdown, postShutdown } from "../api";
import { TaskDetailModal } from "../TaskDetailModal";
import { useParams } from "../parametros";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, ErrorState, Field, Skeleton } from "../ui";

// As 19h: encerrar O TRABALHO. Não é o fechamento das 21h (diário + rotinas) —
// são dois ritos. O entregável daqui são as 3 prioridades de amanhã, que
// reaparecem na Abertura de amanhã.
// Quantos campos, e não "três": o número vem do servidor, via /wiki/parametros.
// Era mais uma cópia — main.py declara PRIORIDADES_SHUTDOWN, o endpoint publica, e a
// tela desenhava 3 fixos. Trocar para 4 fazia o push e a wiki dizerem 4 enquanto esta
// tela continuava com 3 caixas.
function camposDePrioridade(prioridades: string[], quantos: number): string[] {
  return Array.from({ length: quantos }, (_, i) => prioridades[i] ?? "");
}

export default function Shutdown({ onOpenTriagem }: { onOpenTriagem?: () => void } = {}) {
  const { shutdown } = useParams();
  const [data, setData] = useState<ShutdownData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [erro, setErro] = useState("");
  const [campos, setCampos] = useState<string[]>(() =>
    camposDePrioridade([], shutdown.prioridades),
  );
  const [editando, setEditando] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  // `shutdown.prioridades` NAS DEPS: com `[]` o load congelava o valor do primeiro
  // render, e o provider carrega os parâmetros de forma assíncrona — o pull-to-refresh
  // seguia remontando os campos com o número velho depois de o certo ter chegado.
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = await getShutdown();
      setData(s);
      setCampos(camposDePrioridade(s.prioridades, shutdown.prioridades));
      setEditando(false);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [shutdown.prioridades]);

  useEffect(() => {
    load();
  }, [load]);

  async function salvar() {
    // Sem `.slice(0, 3)`. Era a quinta cópia do número — e a pior das cinco, porque
    // as outras só desenhavam ou cortavam no envio: esta DESCARTA o que o Leo
    // escreveu. Com o servidor em 4, ele digitava a quarta prioridade, tocava gravar,
    // e ela sumia sem aviso. O teto já é o número de caixas desenhadas, e o servidor
    // valida contra a mesma constante (422 se sobrar).
    const prioridades = campos.map((c) => c.trim()).filter(Boolean);
    setSalvando(true);
    setErro("");
    try {
      await postShutdown(prioridades);
      setData((cur) => (cur ? { ...cur, prioridades, feito: true } : cur));
      setCampos(camposDePrioridade(prioridades, shutdown.prioridades));
      setEditando(false);
    } catch {
      setErro("não consegui gravar — nada se perdeu, tenta de novo");
    } finally {
      setSalvando(false);
    }
  }

  if (loading) {
    return (
      <View style={{ marginTop: spacing.md }}>
        <Skeleton height={14} style={{ width: 120, marginLeft: 2 }} />
        <Skeleton height={64} />
        <Skeleton height={64} />
        <Skeleton height={160} style={{ marginTop: spacing.md }} />
      </View>
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        message="Não consegui carregar o shutdown."
        hint="O BFF (backend) está rodando na rede? Toque pra tentar de novo."
        onRetry={load}
      />
    );
  }

  const { trabalho_aberto, follow_ups, staging } = data;
  const mostrandoSalvo = data.feito && !editando;
  const podeSalvar = campos.some((c) => c.trim().length > 0);

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingTop: spacing.sm, paddingBottom: spacing.xxl }}
      refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.intro}>
        fecha o trabalho. o que ficou aberto fica aberto — o que importa é sair sabendo o que vem
        amanhã.
      </Text>

      <Text style={styles.label}>TRABALHO AINDA ABERTO</Text>
      {trabalho_aberto.length === 0 ? (
        <Text style={styles.hint}>nada aberto.</Text>
      ) : (
        trabalho_aberto.map((t) => <Linha key={t.id} t={t} onOpen={() => setDetailId(t.id)} />)
      )}

      <Text style={[styles.label, { marginTop: spacing.xl }]}>FOLLOW-UPS</Text>
      {follow_ups.length === 0 ? (
        <Text style={styles.hint}>nenhum follow-up.</Text>
      ) : (
        follow_ups.map((t) => <Linha key={t.id} t={t} onOpen={() => setDetailId(t.id)} />)
      )}

      {staging.n > 0 && (
        <Pressable onPress={onOpenTriagem} disabled={!onOpenTriagem} style={styles.stagingRow}>
          <Text style={styles.staging}>
            staging · {staging.n} {staging.n === 1 ? "item" : "itens"} · mais velho{" "}
            {staging.mais_velho_d}d
          </Text>
          {onOpenTriagem ? (
            <Text style={styles.stagingLink}>triar agora →</Text>
          ) : null}
        </Pressable>
      )}

      <Text style={[styles.label, { marginTop: spacing.xl, marginBottom: spacing.md }]}>
        AS 3 PRIORIDADES DE AMANHÃ
      </Text>

      {!!erro && <Text style={styles.erro}>{erro}</Text>}

      {mostrandoSalvo ? (
        <Card style={{ gap: spacing.md }}>
          {data.prioridades.length === 0 ? (
            <Text style={styles.hint}>nenhuma prioridade gravada.</Text>
          ) : (
            data.prioridades.map((p, i) => (
              <Text key={`p-${i}`} style={styles.prio}>
                <Text style={styles.prioNum}>{i + 1}. </Text>
                {p}
              </Text>
            ))
          )}
          <AppButton title="Editar" variant="ghost" onPress={() => setEditando(true)} />
        </Card>
      ) : (
        <Card style={{ gap: spacing.md }}>
          {/* Uma caixa por prioridade que o servidor pede — não três fixas. */}
          {campos.map((_, i) => (
            <View key={i} style={styles.campoRow}>
              <Text style={styles.campoNum}>{i + 1}</Text>
              <Field
                value={campos[i]}
                onChangeText={(v) =>
                  setCampos((cur) => cur.map((c, idx) => (idx === i ? v : c)))
                }
                placeholder={i === 0 ? "a que importa" : "opcional"}
                style={{ flex: 1 }}
              />
            </View>
          ))}
          <AppButton
            title="Gravar e encerrar o dia de trabalho"
            onPress={salvar}
            loading={salvando}
            disabled={!podeSalvar}
          />
          {data.feito && (
            <AppButton
              title="Cancelar"
              variant="ghost"
              onPress={() => {
                setCampos(camposDePrioridade(data.prioridades, shutdown.prioridades));
                setEditando(false);
                setErro("");
              }}
              disabled={salvando}
            />
          )}
        </Card>
      )}

      <TaskDetailModal
        taskId={detailId}
        onClose={() => setDetailId(null)}
        onComplete={async (id) => {
          await completeTask(id);
          await load();
        }}
        onAdiada={load}
      />
    </ScrollView>
  );
}

// O rito das 19h existe para FECHAR o trabalho. Enquanto a linha era uma View, o
// Leo via o que ficou aberto e não podia fazer nada com aquilo — abre o detalhe,
// que já sabe concluir e adiar.
function Linha({ t, onOpen }: { t: Task; onOpen?: () => void }) {
  const sub = [t.due, t.assignee].filter(Boolean).join(" · ");
  return (
    <Pressable
      onPress={onOpen}
      disabled={!onOpen}
      style={[styles.linha, { borderLeftColor: areaColor(t.area) }]}
    >
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={[styles.area, { color: areaColor(t.area) }]}>{t.area?.toLowerCase()}</Text>
        <Text style={styles.linhaTitulo}>{t.name}</Text>
        {!!sub && <Text style={styles.linhaSub}>{sub}</Text>}
      </View>
      {onOpen ? <Feather name="arrow-up-right" size={15} color={colors.textMuted} /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  stagingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  stagingLink: { fontFamily: fonts.uiSemi, fontSize: 12, color: colors.primary },
  intro: {
    fontFamily: fonts.ui,
    fontSize: 13,
    lineHeight: 19,
    color: colors.textMuted,
    marginBottom: spacing.lg,
  },
  label: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
    letterSpacing: 1.2,
    marginBottom: spacing.sm,
  },
  hint: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, lineHeight: 18 },
  erro: { fontFamily: fonts.ui, fontSize: 13, color: colors.danger, marginBottom: spacing.sm },

  linha: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  area: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1, textTransform: "uppercase" },
  linhaTitulo: { fontFamily: fonts.uiSemi, fontSize: 15, color: colors.text, marginTop: 3 },
  linhaSub: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, marginTop: 2 },

  staging: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
    marginTop: spacing.md,
    lineHeight: 17,
  },

  campoRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  campoNum: { width: 14, fontFamily: fonts.mono, fontSize: 12, color: colors.primary },
  prio: { fontFamily: fonts.ui, fontSize: 15, color: colors.text, lineHeight: 21 },
  prioNum: { fontFamily: fonts.mono, fontSize: 12, color: colors.primary },
});
