import { Feather } from "@expo/vector-icons";
import { useCallback, useEffect, useState } from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  Abertura as AberturaData,
  Nivel,
  RotinaDoDia,
  Template,
  checkRoutine,
  getAbertura,
  postCheckin,
  setTemplateDia,
} from "../api";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, ErrorState, Field, Skeleton } from "../ui";

// A manhã inteira em uma tela: o toque das 5h30 (template), as rotinas da manhã
// marcadas DE MANHÃ (era isso que estava quebrado — só dava pra marcar às 21h),
// o que te espera hoje, e o check-in das 8h20.
const NIVEIS: { key: Nivel; label: string }[] = [
  { key: "baixa", label: "baixa" },
  { key: "media", label: "média" },
  { key: "alta", label: "alta" },
];

function rotuloNivel(v: string | null): string {
  return NIVEIS.find((n) => n.key === v)?.label ?? v ?? "—";
}

export default function Abertura() {
  const [data, setData] = useState<AberturaData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [erro, setErro] = useState("");

  const [trocando, setTrocando] = useState(false);
  const [salvandoTemplate, setSalvandoTemplate] = useState(false);

  const [energia, setEnergia] = useState<Nivel | null>(null);
  const [clareza, setClareza] = useState<Nivel | null>(null);
  const [prioridade, setPrioridade] = useState("");
  const [salvandoCheckin, setSalvandoCheckin] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const a = await getAbertura();
      setData(a);
      setError(false);
      setTrocando(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function escolherTemplate(t: Template) {
    if (!data) return;
    const antes = data;
    setSalvandoTemplate(true);
    setErro("");
    setData({ ...data, template: t });
    try {
      await setTemplateDia(t);
      setTrocando(false);
      // o BFF recalcula as rotinas do dia pelo template — recarrega.
      const a = await getAbertura();
      setData(a);
    } catch {
      setData(antes);
      setErro("não consegui gravar o dia — tenta de novo");
    } finally {
      setSalvandoTemplate(false);
    }
  }

  // Otimista: marca na hora, desfaz se o BFF recusar.
  async function marcar(r: RotinaDoDia) {
    if (!data) return;
    const feito = !r.feito;
    const aplica = (v: boolean) =>
      setData((cur) =>
        cur
          ? {
              ...cur,
              rotinas_manha: cur.rotinas_manha.map((x) =>
                x.slug === r.slug ? { ...x, feito: v } : x,
              ),
            }
          : cur,
      );

    aplica(feito);
    setErro("");
    try {
      await checkRoutine(r.slug, feito);
    } catch {
      aplica(!feito);
      setErro("não consegui marcar — tenta de novo");
    }
  }

  async function salvarCheckin() {
    if (!energia || !clareza) return;
    setSalvandoCheckin(true);
    setErro("");
    try {
      await postCheckin({ energia, clareza, prioridade_1: prioridade.trim() });
      setData((cur) =>
        cur
          ? {
              ...cur,
              checkin: {
                feito: true,
                energia,
                clareza,
                prioridade_1: prioridade.trim(),
              },
            }
          : cur,
      );
    } catch {
      setErro("não consegui salvar o check-in — tenta de novo");
    } finally {
      setSalvandoCheckin(false);
    }
  }

  if (loading) {
    return (
      <View style={{ marginTop: spacing.md }}>
        <Skeleton height={22} style={{ width: 120 }} />
        <Skeleton height={78} />
        <Skeleton height={78} />
        <Skeleton height={120} style={{ marginTop: spacing.md }} />
      </View>
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        message="Não consegui abrir o dia."
        hint="O BFF (backend) está rodando na rede? Toque pra tentar de novo."
        onRetry={load}
      />
    );
  }

  // O toque das 5h30: uma pergunta, duas respostas. Um toque resolve.
  if (data.template === null) {
    return (
      <View style={styles.toque}>
        <Feather name="sunrise" size={30} color={colors.primary} />
        <Text style={styles.toqueTitulo}>como é o dia de hoje?</Text>
        <Text style={styles.toqueHint}>um toque e o dia fica gravado.</Text>

        <View style={styles.toqueBotoes}>
          {(["yoga", "corrida"] as const).map((t) => (
            <Pressable
              key={t}
              onPress={() => escolherTemplate(t)}
              disabled={salvandoTemplate}
              style={({ pressed }) => [
                styles.toqueBtn,
                (pressed || salvandoTemplate) && { opacity: 0.7 },
              ]}
            >
              <Feather
                name={t === "yoga" ? "wind" : "activity"}
                size={22}
                color={colors.primary}
              />
              <Text style={styles.toqueBtnText}>dia {t}</Text>
            </Pressable>
          ))}
        </View>

        {!!erro && <Text style={styles.erro}>{erro}</Text>}
      </View>
    );
  }

  const { rotinas_manha, prioridades_de_ontem, hoje, checkin } = data;
  const feitas = rotinas_manha.filter((r) => r.feito).length;
  const temEspera =
    prioridades_de_ontem.length > 0 ||
    hoje.tarefas_due.length > 0 ||
    hoje.horarios.length > 0;

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingTop: spacing.sm, paddingBottom: spacing.xxl }}
      refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      {/* selo do dia — discreto, com opção de trocar */}
      <View style={styles.seloRow}>
        <View style={styles.selo}>
          <Feather
            name={data.template === "yoga" ? "wind" : "activity"}
            size={12}
            color={colors.primary}
          />
          <Text style={styles.seloText}>dia {data.template}</Text>
        </View>
        <Pressable onPress={() => setTrocando((v) => !v)} hitSlop={8}>
          <Text style={styles.trocar}>{trocando ? "deixa como está" : "trocar"}</Text>
        </Pressable>
      </View>

      {trocando && (
        <View style={styles.pills}>
          {(["yoga", "corrida"] as const).map((t) => {
            const on = t === data.template;
            return (
              <Pressable
                key={t}
                onPress={() => escolherTemplate(t)}
                disabled={salvandoTemplate}
                style={[styles.pill, on && styles.pillOn]}
              >
                <Text style={[styles.pillText, on && styles.pillTextOn]}>dia {t}</Text>
              </Pressable>
            );
          })}
        </View>
      )}

      {!!erro && <Text style={styles.erro}>{erro}</Text>}

      {/* rotinas da manhã — o coração da tela: marcar de manhã, não à noite */}
      <View style={styles.head}>
        <Text style={styles.label}>ROTINAS DA MANHÃ</Text>
        {rotinas_manha.length > 0 && (
          <Text style={styles.placar}>
            {feitas}/{rotinas_manha.length}
          </Text>
        )}
      </View>

      {rotinas_manha.length === 0 ? (
        <Text style={styles.hint}>
          nenhuma rotina de manhã vale hoje — dá pra criar as tuas em Rotinas.
        </Text>
      ) : (
        rotinas_manha.map((r) => (
          <Pressable key={r.slug} onPress={() => marcar(r)} style={styles.rotina}>
            <View style={styles.rotinaTop}>
              <Feather
                name={r.feito ? "check-square" : "square"}
                size={17}
                color={r.feito ? colors.primary : colors.textMuted}
              />
              <Text style={[styles.rotinaNome, r.feito && styles.rotinaNomeOn]}>
                {r.nome}
              </Text>
            </View>

            {r.passos.length > 0 && (
              <View style={styles.passos}>
                {r.passos.map((p, i) => (
                  <Text key={`${r.slug}-${i}`} style={styles.passo}>
                    <Text style={styles.passoNum}>{i + 1}. </Text>
                    {p}
                  </Text>
                ))}
              </View>
            )}
          </Pressable>
        ))
      )}

      {/* o que te espera hoje */}
      {temEspera && (
        <>
          <Text style={[styles.label, { marginTop: spacing.xl, marginBottom: spacing.md }]}>
            O QUE TE ESPERA HOJE
          </Text>

          {prioridades_de_ontem.length > 0 && (
            <Card style={{ gap: spacing.sm, marginBottom: spacing.sm }}>
              <Text style={styles.cardLabel}>você decidiu ontem</Text>
              {prioridades_de_ontem.map((p, i) => (
                <Text key={`prio-${i}`} style={styles.prioOntem}>
                  <Text style={styles.prioNum}>{i + 1}. </Text>
                  {p}
                </Text>
              ))}
            </Card>
          )}

          {hoje.tarefas_due.map((t) => (
            <View
              key={t.id}
              style={[styles.linha, { borderLeftColor: areaColor(t.area) }]}
            >
              <Text style={[styles.area, { color: areaColor(t.area) }]}>
                {t.area?.toLowerCase()}
              </Text>
              <Text style={styles.linhaTitulo}>{t.name}</Text>
              {!!t.due && <Text style={styles.linhaSub}>{t.due}</Text>}
            </View>
          ))}

          {hoje.horarios.map((h, i) => (
            <View key={`h-${i}`} style={styles.horario}>
              <Text style={styles.hora}>{h.hora}</Text>
              <Text style={styles.horaRef}>{h.ref}</Text>
            </View>
          ))}
        </>
      )}

      {/* check-in das 8h20 */}
      <Text style={[styles.label, { marginTop: spacing.xl, marginBottom: spacing.md }]}>
        CHECK-IN
      </Text>

      {checkin.feito ? (
        <Card style={{ gap: spacing.sm }}>
          <View style={styles.estado}>
            <Text style={styles.estadoLabel}>energia</Text>
            <Text style={styles.estadoVal}>{rotuloNivel(checkin.energia)}</Text>
            <Text style={styles.estadoDot}>·</Text>
            <Text style={styles.estadoLabel}>clareza</Text>
            <Text style={styles.estadoVal}>{rotuloNivel(checkin.clareza)}</Text>
          </View>
          {!!checkin.prioridade_1 && (
            <>
              <Text style={styles.cardLabel}>prioridade nº1 de hoje</Text>
              <Text style={styles.prioridade1}>{checkin.prioridade_1}</Text>
            </>
          )}
        </Card>
      ) : (
        <Card style={{ gap: spacing.md }}>
          <View style={{ gap: spacing.sm }}>
            <Text style={styles.label}>ENERGIA</Text>
            <View style={styles.pills}>
              {NIVEIS.map((n) => {
                const on = n.key === energia;
                return (
                  <Pressable
                    key={n.key}
                    onPress={() => setEnergia(n.key)}
                    style={[styles.pill, on && styles.pillOn]}
                  >
                    <Text style={[styles.pillText, on && styles.pillTextOn]}>{n.label}</Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          <View style={{ gap: spacing.sm }}>
            <Text style={styles.label}>CLAREZA</Text>
            <View style={styles.pills}>
              {NIVEIS.map((n) => {
                const on = n.key === clareza;
                return (
                  <Pressable
                    key={n.key}
                    onPress={() => setClareza(n.key)}
                    style={[styles.pill, on && styles.pillOn]}
                  >
                    <Text style={[styles.pillText, on && styles.pillTextOn]}>{n.label}</Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          <View style={{ gap: spacing.sm }}>
            <Text style={styles.label}>QUAL É A PRIORIDADE Nº1 DE HOJE?</Text>
            <Field
              value={prioridade}
              onChangeText={setPrioridade}
              placeholder="uma linha — a que importa"
            />
          </View>

          <AppButton
            title="Salvar check-in"
            onPress={salvarCheckin}
            loading={salvandoCheckin}
            disabled={!energia || !clareza}
          />
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  toque: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  toqueTitulo: {
    fontFamily: fonts.serif,
    fontSize: 28,
    color: colors.text,
    textAlign: "center",
    marginTop: spacing.sm,
    letterSpacing: -0.3,
  },
  toqueHint: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  toqueBotoes: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.xl,
    alignSelf: "stretch",
  },
  toqueBtn: {
    flex: 1,
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xl,
    backgroundColor: colors.card,
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radius.lg,
  },
  toqueBtnText: { fontFamily: fonts.uiSemi, fontSize: 17, color: colors.text },

  seloRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  selo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.primarySoft,
    borderRadius: radius.pill,
    paddingHorizontal: 11,
    paddingVertical: 5,
  },
  seloText: { fontFamily: fonts.mono, fontSize: 11, color: colors.primary },
  trocar: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted },

  head: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  label: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted, letterSpacing: 1.2 },
  placar: { fontFamily: fonts.mono, fontSize: 11, color: colors.primary },
  hint: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, lineHeight: 18 },
  erro: { fontFamily: fonts.ui, fontSize: 13, color: colors.danger, marginBottom: spacing.sm },

  rotina: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  rotinaTop: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  rotinaNome: { flex: 1, fontFamily: fonts.uiSemi, fontSize: 15.5, color: colors.text },
  rotinaNomeOn: { color: colors.primary },
  passos: { marginTop: spacing.sm, marginLeft: 25, gap: 2 },
  passo: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, lineHeight: 18 },
  passoNum: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted },

  cardLabel: {
    fontFamily: fonts.mono,
    fontSize: 10.5,
    color: colors.textMuted,
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  prioOntem: { fontFamily: fonts.ui, fontSize: 14.5, color: colors.text, lineHeight: 20 },
  prioNum: { fontFamily: fonts.mono, fontSize: 12, color: colors.primary },

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

  horario: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: 7,
  },
  hora: { fontFamily: fonts.mono, fontSize: 12, color: colors.primary, minWidth: 44 },
  horaRef: { flex: 1, fontFamily: fonts.ui, fontSize: 14, color: colors.text },

  estado: { flexDirection: "row", alignItems: "center", gap: 7, flexWrap: "wrap" },
  estadoLabel: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted },
  estadoVal: { fontFamily: fonts.mono, fontSize: 11, color: colors.primary },
  estadoDot: { color: colors.textMuted, fontSize: 11 },
  prioridade1: { fontFamily: fonts.serif, fontSize: 17, color: colors.text, lineHeight: 24 },

  pills: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.md },
  pill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  pillOn: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  pillText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  pillTextOn: { color: colors.primary, fontFamily: fonts.uiSemi },
});
