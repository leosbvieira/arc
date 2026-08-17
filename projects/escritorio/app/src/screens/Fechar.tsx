import Feather from "@expo/vector-icons/Feather";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, BackHandler, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import {
  Bloco,
  ClosingRotina,
  Pontos,
  Template,
  closingApprove,
  closingDraft,
  checkRoutine,
  closingRoutines,
  getPontos,
  getAbertura,
  setTemplateDia,
} from "../api";
import { buildClosingChecks, seedDecisions } from "../closingChecks";
import { closingLabel, closingReward } from "../closingPoints";
import { useParams } from "../parametros";
import { colors, fonts, spacing } from "../theme";
import { BigAction, QuestRow, RewardSheet } from "../ui";

// As rotinas já vêm filtradas pelo BFF (dia da semana + template). Não filtre aqui.
// Os passos são roteiro: aparecem numerados em cinza, SEM checkbox próprio — quem
// conta no fechamento é o item pai, binário.
//
// O template NÃO se escolhe aqui: é o toque das 5h30, na Abertura. Aqui a gente só
// lê (`GET /abertura`). O seletor só aparece como fallback, se o dia não foi marcado.
// E as rotinas da manhã já podem estar marcadas — o estado da manhã manda; montar a
// tela NÃO zera nada.
const BLOCOS: { key: Bloco; label: string }[] = [
  { key: "manha", label: "Manhã" },
  { key: "dia", label: "Dia" },
  { key: "noite", label: "Noite" },
];

// Ação secundária do rito (design: ghostact) — nunca compete com o bronze do
// BigAction: borda fina, mono miúdo, muted.
function GhostAction({
  title,
  icon,
  onPress,
  disabled,
  loading,
}: {
  title: string;
  icon?: React.ComponentProps<typeof Feather>["name"];
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        {
          minHeight: 44,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          borderWidth: 1,
          borderColor: colors.border,
          borderRadius: 12,
        },
        (disabled || loading) && { opacity: 0.45 },
        pressed && { opacity: 0.7 },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={colors.textMuted} size="small" />
      ) : (
        <>
          {icon ? <Feather name={icon} size={13} color={colors.textMuted} /> : null}
          <Text
            style={{
              fontFamily: fonts.mono,
              fontSize: 10.5,
              letterSpacing: 0.5,
              color: colors.textMuted,
            }}
          >
            {title}
          </Text>
        </>
      )}
    </Pressable>
  );
}

export default function Fechar() {
  const { tarifas } = useParams();
  const [template, setTemplate] = useState<Template | null>(null);
  const [loadingDia, setLoadingDia] = useState(true);
  const [routines, setRoutines] = useState<ClosingRotina[]>([]);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [dump, setDump] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [gerando, setGerando] = useState(false);
  const [done, setDone] = useState(false);
  const [pontosFecho, setPontosFecho] = useState(0);
  const [err, setErr] = useState("");
  const [loadingRoutines, setLoadingRoutines] = useState(false);
  const [routinesErr, setRoutinesErr] = useState("");
  const [routinesReload, setRoutinesReload] = useState(0);
  const [placar, setPlacar] = useState<Pontos | null>(null);

  // Só o dia (template) vem da abertura. O que já foi marcado NÃO se reconstrói
  // aqui: `/closing/routines` devolve `feito` para o dia inteiro, e a abertura só
  // conhecia o bloco da manhã — reconstruir no cliente era a origem do bug que
  // apagava as marcações no fechamento.
  useEffect(() => {
    let alive = true;

    getAbertura()
      .then((a) => {
        if (!alive) return;
        setTemplate(a.template);
      })
      .catch(() => {
        // sem abertura, cai no seletor de fallback abaixo.
        if (alive) setTemplate(null);
      })
      .finally(() => {
        if (alive) setLoadingDia(false);
      });

    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;

    if (template === null) {
      setLoadingRoutines(false);
      setRoutines([]);
      return;
    }

    setLoadingRoutines(true);
    setRoutines([]);
    setRoutinesErr("");

    closingRoutines(template)
      .then((rs) => {
        if (!alive) return;
        setRoutines(rs);
        // O servidor é a fonte do estado do dia (`feito`). Decisão já tomada nesta
        // tela vence a semente; rotina sem decisão fica FORA do objeto — ausência
        // não é furo, e é isso que impede o fechamento de apagar a manhã.
        setChecks((current) => ({ ...seedDecisions(rs), ...current }));
      })
      .catch(() => {
        if (!alive) return;
        setRoutines([]);
        setRoutinesErr("sem conexão com o BFF");
      })
      .finally(() => {
        if (alive) setLoadingRoutines(false);
      });

    return () => {
      alive = false;
    };
  }, [template, routinesReload]);

  // Marca na hora, igual à Abertura. Antes o fechamento só gravava junto com o
  // diário — e os DOIS botões exigiam texto, inclusive o "modo mínimo". Ou seja:
  // não dava para registrar as rotinas sem escrever. Era essa assimetria que
  // produzia os dias sem registro (e "linha ausente" some do scorecard).
  const marcar = async (slug: string) => {
    const feito = !checks[slug];
    setChecks((current) => ({ ...current, [slug]: feito }));
    try {
      await checkRoutine(slug, feito);
    } catch {
      setChecks((current) => ({ ...current, [slug]: !feito }));
      setErr("não consegui marcar — tenta de novo");
    }
  };

  const gerar = async () => {
    if (!template) return;
    setGerando(true);
    setErr("");
    try {
      setDraft(await closingDraft(dump, template));
    } catch {
      setErr("não consegui estruturar — tenta de novo ou grava direto");
    } finally {
      setGerando(false);
    }
  };

  // UMA regra para "tem texto": o despejo preenchido OU um rascunho existente.
  // A mesma constante alimenta o rótulo do BigAction (a promessa) e o cálculo da
  // RewardSheet (o pagamento) — divergir aqui é prometer +40 e pagar 40 a menos.
  const temTexto = !!dump.trim() || draft !== null;

  const aprovar = async (md: string) => {
    if (!template) return;
    setBusy(true);
    setErr("");
    try {
      await closingApprove({
        raw_text: dump,
        draft_md: md,
        template,
        checks: buildClosingChecks(routines, checks),
      });
      // O número que a RewardSheet mostra é o que o botão prometeu (tabela de
      // tarifas, display-only) — o saldo oficial chega pelo getPontos() abaixo.
      const marcadas = routines.filter((r) => checks[r.slug]).length;
      setPontosFecho(closingReward(marcadas, routines.length, temTexto, tarifas).garantido);
      setDone(true);
      getPontos().then(setPlacar).catch(() => {/* o placar é bônus, não trava o fecho */});
    } catch {
      setErr("falha ao gravar — nada se perdeu, tenta de novo");
    } finally {
      setBusy(false);
    }
  };

  // Fallback: o dia não foi marcado de manhã. Marca agora, e grava (é o mesmo dia).
  const selectTemplate = (next: Template) => {
    if (next === template) return;
    setTemplate(next);
    setTemplateDia(next).catch(() => {
      /* offline: segue com o template local, o approve leva o template junto */
    });
  };

  const retryRoutines = () => {
    setLoadingRoutines(true);
    setRoutinesReload((current) => current + 1);
  };

  // Lista vazia agora é legítima (ex.: só tem rotina de quarta e hoje é terça) —
  // o que trava o fechamento é não ter conseguido carregar, não ter zero rotinas.
  const routinesUnavailable =
    loadingDia || template === null || loadingRoutines || !!routinesErr;
  const dumpActionsDisabled = busy || gerando || routinesUnavailable || !dump.trim();
  // O modo mínimo fecha o dia mesmo sem diário: as rotinas já foram gravadas por
  // toque, e obrigar a escrever é o que fazia o dia ruim virar dia não-registrado.
  // Escrever nunca é portão — o despejo é bônus opcional abaixo do botão.
  const fecharDisabled = busy || gerando || routinesUnavailable;

  // O rótulo do BigAction: o que o toque garante agora e o máximo do dia.
  const marcadas = routines.filter((r) => checks[r.slug]).length;

  if (done) {
    // O único momento de dopamina do dia era uma linha de texto. Se o design declara
    // "check visível" como lei, o fim do rito tem que devolver o que ele produziu.
    // A C também corrige a saída: "Boa noite" encerra o app; o ghost devolve ao
    // rito para rever o que ficou sem marcar (o registro já está gravado).
    const feitas = routines.filter((r) => checks[r.slug]).length;
    return (
      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}>
        <RewardSheet
          pontosHoje={pontosFecho}
          placar={placar}
          ritmosFeitos={feitas}
          ritmosTotal={routines.length}
          onBoaNoite={() => BackHandler.exitApp()}
          onVerSemMarcar={() => setDone(false)}
        />
      </ScrollView>
    );
  }

  return (
    <ScrollView style={{ flex: 1, padding: 16 }}>
      {loadingDia ? (
        <ActivityIndicator color={colors.primary} style={{ alignSelf: "flex-start" }} />
      ) : template === null ? (
        <>
          <Text style={{ color: colors.textMuted, fontFamily: fonts.ui }}>
            o dia não foi marcado de manhã — qual foi?
          </Text>
          <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
            {(["yoga", "corrida"] as const).map((t) => (
              <Pressable
                key={t}
                onPress={() => selectTemplate(t)}
                style={{ padding: 8, borderRadius: 8, backgroundColor: colors.card }}
              >
                <Text style={{ color: colors.text }}>dia {t}</Text>
              </Pressable>
            ))}
          </View>
        </>
      ) : (
        <Text
          style={{
            color: colors.textMuted,
            fontFamily: fonts.mono,
            fontSize: 9,
            letterSpacing: 1.5,
            textTransform: "uppercase",
          }}
        >
          rito da noite · dia {template}
        </Text>
      )}

      {loadingRoutines ? (
        <ActivityIndicator
          color={colors.primary}
          style={{ alignSelf: "flex-start", marginTop: 16 }}
        />
      ) : template === null ? (
        <Text style={{ color: colors.textMuted, marginTop: 16, fontFamily: fonts.ui }}>
          marca o dia acima pra ver as rotinas.
        </Text>
      ) : routines.length === 0 && !routinesErr ? (
        <Text style={{ color: colors.textMuted, marginTop: 16, fontFamily: fonts.ui }}>
          nenhuma rotina vale hoje — dá pra criar as tuas em Rotinas.
        </Text>
      ) : (
        BLOCOS.map((b) => {
          const doBloco = routines.filter((r) => r.bloco === b.key);
          if (doBloco.length === 0) return null;
          const feitas = doBloco.filter((r) => checks[r.slug]).length;
          return (
            <View key={b.key} style={{ marginTop: spacing.md }}>
              {/* Régua de bloco aprovada na C: eyebrow mono, filete, contagem. */}
              <View
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  marginHorizontal: 2,
                  marginBottom: spacing.sm,
                }}
              >
                <Text
                  style={{
                    fontFamily: fonts.mono,
                    fontSize: 9,
                    color: colors.textMuted,
                    textTransform: "uppercase",
                    letterSpacing: 1.8,
                  }}
                >
                  {b.label}
                </Text>
                <View
                  style={{
                    flex: 1,
                    height: 1,
                    backgroundColor: colors.border,
                    marginHorizontal: 10,
                  }}
                />
                <Text style={{ fontFamily: fonts.mono, fontSize: 9, color: colors.faint }}>
                  {feitas}/{doBloco.length}
                  {feitas > 0 ? ` · +${feitas * tarifas.rotina}` : ""}
                </Text>
              </View>

              {doBloco.map((r) => (
                <QuestRow
                  key={r.slug}
                  name={r.nome}
                  done={!!checks[r.slug]}
                  points={tarifas.rotina}
                  steps={r.passos}
                  onPress={() => marcar(r.slug)}
                />
              ))}
            </View>
          );
        })
      )}

      {!!routinesErr && (
        <View style={{ marginTop: 8, alignItems: "flex-start" }}>
          <Text style={{ color: colors.danger }}>{routinesErr}</Text>
          <Pressable
            onPress={retryRoutines}
            disabled={loadingRoutines}
            style={{ marginTop: 6 }}
          >
            <Text style={{ color: colors.primary }}>
              tentar carregar novamente
            </Text>
          </Pressable>
        </View>
      )}

      {draft === null ? (
        <>
          {/* Despejo da decisão 11=B: a pergunta vira o placeholder do próprio
              campo — sem label duplicado em cima da caixa. */}
          <TextInput
            multiline
            value={dump}
            onChangeText={setDump}
            placeholder="como foi o dia? — opcional, vale bônus"
            placeholderTextColor={colors.textMuted}
            style={{
              minHeight: 64,
              color: colors.text,
              backgroundColor: colors.card,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: 12,
              padding: 12,
              marginTop: 16,
              textAlignVertical: "top",
            }}
          />
          <View style={{ marginTop: 10 }}>
            <GhostAction
              title={`estruturar com o Hermes · +${tarifas.despejo} bônus`}
              icon="star"
              onPress={gerar}
              disabled={dumpActionsDisabled}
              loading={gerando}
            />
          </View>
          <View style={{ marginTop: 12 }}>
            <BigAction
              title="Fechar o dia"
              sub={closingLabel(marcadas, routines.length, temTexto, tarifas)}
              onPress={() => aprovar(dump)}
              disabled={fecharDisabled}
              loading={busy}
            />
          </View>
        </>
      ) : (
        <>
          <Text style={{ color: colors.textMuted, marginTop: 16 }}>
            rascunho — edita à vontade, gravo exatamente isto
          </Text>
          <TextInput
            multiline
            value={draft}
            onChangeText={setDraft}
            style={{
              minHeight: 200,
              color: colors.text,
              backgroundColor: colors.card,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: 12,
              padding: 12,
              marginTop: 8,
            }}
          />
          <View style={{ marginTop: 12 }}>
            <BigAction
              title="Aprovar e gravar"
              sub={closingLabel(marcadas, routines.length, temTexto, tarifas)}
              onPress={() => aprovar(draft)}
              disabled={busy}
              loading={busy}
            />
          </View>
          <View style={{ marginTop: 10 }}>
            <GhostAction
              title="← voltar ao despejo"
              onPress={() => setDraft(null)}
              disabled={busy}
            />
          </View>
        </>
      )}
      {!!err && (
        <Text style={{ color: colors.danger, marginTop: 12 }}>
          {err}
        </Text>
      )}
    </ScrollView>
  );
}
