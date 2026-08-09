import { Feather } from "@expo/vector-icons";
import * as SecureStore from "../storage";
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
  Abertura as AberturaData,
  Nivel,
  RotinaDoDia,
  Template,
  addTema,
  checkRoutine,
  createGoogleCalendarEvent,
  deleteTema,
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

const GOOGLE_EVENT_PENDING_KEY = "google_calendar_event_pending";

type PendingGoogleEvent = {
  client_key: string;
  body: { titulo: string; data: string; hora: string; duracao_min: number };
};

function rotuloNivel(v: string | null): string {
  return NIVEIS.find((n) => n.key === v)?.label ?? v ?? "—";
}

function rotuloFonte(v: string): string {
  if (v === "ok") return "ao vivo";
  if (v === "cache") return "cache";
  if (v === "nao_configurado") return "não ligado";
  return "indisponível";
}

function hojeNoAparelho(): string {
  const agora = new Date();
  const ano = agora.getFullYear();
  const mes = String(agora.getMonth() + 1).padStart(2, "0");
  const dia = String(agora.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

function novaChaveEvento(): string {
  return `gcal-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
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
  const [novoTema, setNovoTema] = useState("");
  const [salvandoTema, setSalvandoTema] = useState(false);
  const [mostrarEvento, setMostrarEvento] = useState(false);
  const [eventoTitulo, setEventoTitulo] = useState("");
  const [eventoData, setEventoData] = useState(hojeNoAparelho);
  const [eventoHora, setEventoHora] = useState("09:00");
  const [eventoDuracao, setEventoDuracao] = useState("60");
  const [eventoClientKey, setEventoClientKey] = useState(novaChaveEvento);
  const [criandoEvento, setCriandoEvento] = useState(false);
  const [eventoPendente, setEventoPendente] = useState(false);

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

  useEffect(() => {
    SecureStore.getItemAsync(GOOGLE_EVENT_PENDING_KEY)
      .then(async (raw) => {
        if (!raw) return;
        try {
          const pending = JSON.parse(raw) as PendingGoogleEvent;
          if (!pending.client_key || !pending.body?.titulo) throw new Error("invalid pending");
          setEventoTitulo(pending.body.titulo);
          setEventoData(pending.body.data);
          setEventoHora(pending.body.hora);
          setEventoDuracao(String(pending.body.duracao_min));
          setEventoClientKey(pending.client_key);
          setEventoPendente(true);
          setMostrarEvento(true);
        } catch {
          await SecureStore.deleteItemAsync(GOOGLE_EVENT_PENDING_KEY);
        }
      })
      .catch(() => undefined);
  }, []);

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

  async function criarTema() {
    const texto = novoTema.trim();
    if (!texto || !data) return;
    setSalvandoTema(true);
    setErro("");
    try {
      const tema = await addTema(texto);
      setData({ ...data, temas: [...data.temas, tema] });
      setNovoTema("");
    } catch {
      setErro("não consegui salvar o tema da semana");
    } finally {
      setSalvandoTema(false);
    }
  }

  async function removerTema(id: number) {
    if (!data) return;
    const anterior = data.temas;
    setData({ ...data, temas: anterior.filter((tema) => tema.id !== id) });
    try {
      await deleteTema(id);
    } catch {
      setData((atual) => (atual ? { ...atual, temas: anterior } : atual));
      setErro("não consegui remover o tema da semana");
    }
  }

  function confirmarEventoGoogle() {
    const titulo = eventoTitulo.trim();
    const duracao = Number(eventoDuracao);
    if (!titulo) return;
    if (!Number.isInteger(duracao) || duracao < 5 || duracao > 720) {
      Alert.alert("Google Calendar", "A duração precisa estar entre 5 e 720 minutos.");
      return;
    }

    Alert.alert(
      "Inserir no Google pessoal",
      `${titulo}\n${eventoData} às ${eventoHora} · ${duracao} min`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Inserir evento",
          onPress: async () => {
            setCriandoEvento(true);
            try {
              const body = {
                titulo,
                data: eventoData,
                hora: eventoHora,
                duracao_min: duracao,
              };
              let clientKey = eventoClientKey;
              const salvo = await SecureStore.getItemAsync(GOOGLE_EVENT_PENDING_KEY);
              if (salvo) {
                try {
                  const pending = JSON.parse(salvo) as PendingGoogleEvent;
                  if (JSON.stringify(pending.body) === JSON.stringify(body)) {
                    clientKey = pending.client_key;
                  }
                } catch {
                  // O set abaixo substitui qualquer estado local corrompido.
                }
              }
              const pending: PendingGoogleEvent = { client_key: clientKey, body };
              await SecureStore.setItemAsync(GOOGLE_EVENT_PENDING_KEY, JSON.stringify(pending));
              setEventoPendente(true);

              const evento = await createGoogleCalendarEvent({ ...body, client_key: clientKey });
              if (data?.data === eventoData) {
                setData((atual) =>
                  atual
                    ? atual.hoje.calendario.some(
                        (item) =>
                          item.fonte === "gcal" &&
                          item.titulo === evento.titulo &&
                          item.hora === eventoHora,
                      )
                      ? atual
                      : {
                        ...atual,
                        hoje: {
                          ...atual.hoje,
                          calendario: [
                            ...atual.hoje.calendario,
                            { hora: eventoHora, titulo: evento.titulo, fonte: "gcal" },
                          ],
                        },
                      }
                    : atual,
                );
              }
              await SecureStore.deleteItemAsync(GOOGLE_EVENT_PENDING_KEY);
              setEventoPendente(false);
              setEventoTitulo("");
              setEventoClientKey(novaChaveEvento());
              setMostrarEvento(false);
              Alert.alert("Google Calendar", "Evento inserido no calendário pessoal.");
            } catch (e: any) {
              if (
                e?.name === "GoogleCalendarNotConfigured" ||
                e?.name === "GoogleCalendarHttp422"
              ) {
                await SecureStore.deleteItemAsync(GOOGLE_EVENT_PENDING_KEY);
                setEventoPendente(false);
              }
              Alert.alert("Google Calendar", e?.message ?? "não consegui inserir o evento");
            } finally {
              setCriandoEvento(false);
            }
          },
        },
      ],
    );
  }

  function abandonarEventoPendente() {
    Alert.alert(
      "Abandonar envio pendente",
      "Isto libera a edição, mas não remove um evento que talvez já tenha chegado ao Google.",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Abandonar",
          style: "destructive",
          onPress: async () => {
            try {
              await SecureStore.deleteItemAsync(GOOGLE_EVENT_PENDING_KEY);
              setEventoPendente(false);
              setEventoClientKey(novaChaveEvento());
            } catch {
              Alert.alert("Google Calendar", "Não consegui limpar o envio pendente.");
            }
          },
        },
      ],
    );
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

  const { rotinas_manha, prioridades_de_ontem, hoje, checkin, temas } = data;
  const feitas = rotinas_manha.filter((r) => r.feito).length;
  const temEspera =
    prioridades_de_ontem.length > 0 ||
    hoje.tarefas_due.length > 0 ||
    hoje.horarios.length > 0 ||
    hoje.calendario.length > 0 ||
    Object.keys(hoje.fontes_calendario).length > 0;

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

      <Text style={[styles.label, { marginTop: spacing.xl, marginBottom: spacing.md }]}>TEMAS DA SEMANA</Text>
      <Card style={{ gap: spacing.sm }}>
        {temas.length > 0 ? (
          temas.map((tema) => (
            <View key={tema.id} style={styles.temaRow}>
              <Feather name="bookmark" size={13} color={colors.primary} />
              <Text style={styles.temaTexto}>{tema.texto}</Text>
              <Pressable onPress={() => removerTema(tema.id)} hitSlop={8}>
                <Feather name="x" size={15} color={colors.textMuted} />
              </Pressable>
            </View>
          ))
        ) : (
          <Text style={styles.hint}>nenhum tema definido para esta semana.</Text>
        )}
        <View style={styles.temaNovo}>
          <Field
            value={novoTema}
            onChangeText={setNovoTema}
            placeholder="ex.: marcar médico"
            style={{ flex: 1 }}
            onSubmitEditing={criarTema}
          />
          <Pressable
            onPress={criarTema}
            disabled={!novoTema.trim() || salvandoTema}
            style={[styles.temaAdd, (!novoTema.trim() || salvandoTema) && { opacity: 0.45 }]}
          >
            <Feather name="plus" size={18} color={colors.primaryText} />
          </Pressable>
        </View>
      </Card>

      <View style={styles.googleHead}>
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>GOOGLE CALENDAR PESSOAL</Text>
          <Text style={styles.hint}>inserção explícita · Outlook continua só leitura</Text>
        </View>
        <Pressable
          onPress={() => setMostrarEvento((valor) => !valor)}
          disabled={eventoPendente}
          style={[styles.googleToggle, eventoPendente && { opacity: 0.5 }]}
        >
          <Feather name={mostrarEvento ? "x" : "plus"} size={15} color={colors.primary} />
          <Text style={styles.googleToggleText}>
            {eventoPendente ? "envio pendente" : mostrarEvento ? "fechar" : "novo evento"}
          </Text>
        </Pressable>
      </View>

      {mostrarEvento ? (
        <Card style={styles.googleForm}>
          {eventoPendente ? (
            <View style={styles.pendingEvent}>
              <Feather name="alert-circle" size={15} color={colors.amber} />
              <Text style={styles.pendingEventText}>
                Resultado incerto. Tente novamente sem editar para reconciliar o mesmo evento.
              </Text>
            </View>
          ) : null}
          <Text style={styles.cardLabel}>título</Text>
          <Field
            value={eventoTitulo}
            editable={!eventoPendente}
            onChangeText={(valor) => {
              setEventoTitulo(valor);
              setEventoClientKey(novaChaveEvento());
            }}
            placeholder="evento no Google pessoal"
          />
          <View style={styles.googleFields}>
            <View style={{ flex: 1.4, gap: spacing.xs }}>
              <Text style={styles.cardLabel}>data</Text>
              <Field
                value={eventoData}
                editable={!eventoPendente}
                onChangeText={(valor) => {
                  setEventoData(valor);
                  setEventoClientKey(novaChaveEvento());
                }}
                placeholder="YYYY-MM-DD"
                keyboardType="numbers-and-punctuation"
              />
            </View>
            <View style={{ flex: 1, gap: spacing.xs }}>
              <Text style={styles.cardLabel}>hora</Text>
              <Field
                value={eventoHora}
                editable={!eventoPendente}
                onChangeText={(valor) => {
                  setEventoHora(valor);
                  setEventoClientKey(novaChaveEvento());
                }}
                placeholder="HH:MM"
                keyboardType="numbers-and-punctuation"
              />
            </View>
          </View>
          <Text style={styles.cardLabel}>duração em minutos</Text>
          <Field
            value={eventoDuracao}
            editable={!eventoPendente}
            onChangeText={(valor) => {
              setEventoDuracao(valor);
              setEventoClientKey(novaChaveEvento());
            }}
            placeholder="60"
            keyboardType="number-pad"
          />
          <AppButton
            title={eventoPendente ? "Tentar novamente" : "Revisar inserção"}
            onPress={confirmarEventoGoogle}
            loading={criandoEvento}
            disabled={!eventoTitulo.trim() || !eventoData.trim() || !eventoHora.trim()}
          />
          {eventoPendente ? (
            <Pressable onPress={abandonarEventoPendente} disabled={criandoEvento}>
              <Text style={styles.abandonEvent}>abandonar envio pendente</Text>
            </Pressable>
          ) : null}
        </Card>
      ) : null}

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

          {hoje.calendario.length > 0 && (
            <Card style={{ gap: spacing.sm, marginTop: spacing.sm }}>
              <View style={styles.calHead}>
                <Text style={styles.cardLabel}>calendário</Text>
                <View style={styles.fontes}>
                  {Object.entries(hoje.fontes_calendario).map(([fonte, estado]) => (
                    <Text key={fonte} style={styles.fonte}>
                      {fonte} · {rotuloFonte(estado)}
                    </Text>
                  ))}
                </View>
              </View>
              {hoje.calendario.map((evento, i) => (
                <View key={`${evento.fonte}-${evento.titulo}-${i}`} style={styles.horario}>
                  <Text style={styles.hora}>{evento.hora ?? "dia"}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.horaRef}>{evento.titulo}</Text>
                    <Text style={styles.eventoFonte}>{evento.fonte}</Text>
                  </View>
                </View>
              ))}
            </Card>
          )}

          {hoje.calendario.length === 0 && Object.keys(hoje.fontes_calendario).length > 0 && (
            <View style={styles.fontesLinha}>
              {Object.entries(hoje.fontes_calendario).map(([fonte, estado]) => (
                <Text key={fonte} style={styles.fonte}>
                  {fonte} · {rotuloFonte(estado)}
                </Text>
              ))}
            </View>
          )}
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
    fontFamily: fonts.display,
    fontSize: 28,
    color: colors.text,
    textAlign: "center",
    marginTop: spacing.sm,
    letterSpacing: -0.15,
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
  eventoFonte: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, marginTop: 2 },
  calHead: { gap: spacing.xs },
  fontes: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  fontesLinha: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.sm },
  fonte: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted },
  temaRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  temaTexto: { flex: 1, fontFamily: fonts.ui, fontSize: 14, color: colors.text, lineHeight: 20 },
  temaNovo: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.xs },
  temaAdd: {
    width: 46,
    height: 46,
    borderRadius: radius.md,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  googleHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
  },
  googleToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  googleToggleText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.primary },
  googleForm: { gap: spacing.sm, marginBottom: spacing.sm },
  googleFields: { flexDirection: "row", gap: spacing.sm },
  pendingEvent: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, padding: spacing.sm, borderRadius: radius.md, backgroundColor: colors.card2 },
  pendingEventText: { flex: 1, fontFamily: fonts.ui, fontSize: 12, lineHeight: 17, color: colors.textMuted },
  abandonEvent: { fontFamily: fonts.ui, fontSize: 12, color: colors.textMuted, textAlign: "center", paddingVertical: spacing.xs },

  estado: { flexDirection: "row", alignItems: "center", gap: 7, flexWrap: "wrap" },
  estadoLabel: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted },
  estadoVal: { fontFamily: fonts.mono, fontSize: 11, color: colors.primary },
  estadoDot: { color: colors.textMuted, fontSize: 11 },
  prioridade1: { fontFamily: fonts.ui, fontSize: 17, color: colors.text, lineHeight: 24 },

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
