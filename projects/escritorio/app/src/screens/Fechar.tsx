import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { Bloco, ClosingRotina, closingApprove, closingDraft, closingRoutines } from "../api";
import { colors, fonts, spacing } from "../theme";

// As rotinas já vêm filtradas pelo BFF (dia da semana + template). Não filtre aqui.
// Os passos são roteiro: aparecem numerados em cinza, SEM checkbox próprio — quem
// conta no fechamento é o item pai, binário.
const BLOCOS: { key: Bloco; label: string }[] = [
  { key: "manha", label: "Manhã" },
  { key: "dia", label: "Dia" },
  { key: "noite", label: "Noite" },
];

export default function Fechar() {
  const [template, setTemplate] = useState<"yoga" | "corrida">("yoga");
  const [routines, setRoutines] = useState<ClosingRotina[]>([]);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [dump, setDump] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const [loadingRoutines, setLoadingRoutines] = useState(true);
  const [routinesErr, setRoutinesErr] = useState("");
  const [routinesReload, setRoutinesReload] = useState(0);

  useEffect(() => {
    let alive = true;

    setLoadingRoutines(true);
    setRoutines([]);
    setChecks({});
    setRoutinesErr("");

    closingRoutines(template)
      .then((rs) => {
        if (!alive) return;
        setRoutines(rs);
        setChecks(Object.fromEntries(rs.map((r) => [r.slug, false])));
      })
      .catch(() => {
        if (!alive) return;
        setRoutines([]);
        setChecks({});
        setRoutinesErr("sem conexão com o BFF");
      })
      .finally(() => {
        if (alive) setLoadingRoutines(false);
      });

    return () => {
      alive = false;
    };
  }, [template, routinesReload]);

  const gerar = async () => {
    setBusy(true);
    setErr("");
    try {
      setDraft(await closingDraft(dump, template));
    } catch {
      setErr("não consegui estruturar — tenta de novo ou grava direto");
    } finally {
      setBusy(false);
    }
  };

  const aprovar = async (md: string) => {
    setBusy(true);
    setErr("");
    try {
      await closingApprove({
        raw_text: dump,
        draft_md: md,
        template,
        checks: routines.map((r) => ({
          rotina: r.slug,
          feito: !!checks[r.slug],
        })),
      });
      setDone(true);
    } catch {
      setErr("falha ao gravar — nada se perdeu, tenta de novo");
    } finally {
      setBusy(false);
    }
  };

  const selectTemplate = (next: "yoga" | "corrida") => {
    if (next === template) return;
    setLoadingRoutines(true);
    setRoutines([]);
    setChecks({});
    setRoutinesErr("");
    setTemplate(next);
  };

  const retryRoutines = () => {
    setLoadingRoutines(true);
    setRoutinesReload((current) => current + 1);
  };

  // Lista vazia agora é legítima (ex.: só tem rotina de quarta e hoje é terça) —
  // o que trava o fechamento é não ter conseguido carregar, não ter zero rotinas.
  const routinesUnavailable = loadingRoutines || !!routinesErr;
  const dumpActionsDisabled =
    busy || routinesUnavailable || !dump.trim();

  if (done) {
    return (
      <View style={{ padding: 24 }}>
        <Text style={{ color: colors.text, fontSize: 18 }}>
          ✓ dia fechado
        </Text>
      </View>
    );
  }

  return (
    <ScrollView style={{ flex: 1, padding: 16 }}>
      <View style={{ flexDirection: "row", gap: 8 }}>
        {(["yoga", "corrida"] as const).map((t) => (
          <Pressable
            key={t}
            onPress={() => selectTemplate(t)}
            style={{
              padding: 8,
              borderRadius: 8,
              backgroundColor:
                template === t ? colors.primary : colors.card,
            }}
          >
            <Text style={{ color: template === t ? colors.primaryText : colors.text }}>
              dia {t}
            </Text>
          </Pressable>
        ))}
      </View>

      <Text style={{ color: colors.textMuted, marginTop: 16 }}>
        rotinas de hoje
      </Text>
      {loadingRoutines ? (
        <ActivityIndicator
          color={colors.primary}
          style={{ alignSelf: "flex-start", marginTop: 8 }}
        />
      ) : routines.length === 0 && !routinesErr ? (
        <Text style={{ color: colors.textMuted, marginTop: 8, fontFamily: fonts.ui }}>
          nenhuma rotina vale hoje — dá pra criar as tuas em Rotinas.
        </Text>
      ) : (
        BLOCOS.map((b) => {
          const doBloco = routines.filter((r) => r.bloco === b.key);
          if (doBloco.length === 0) return null;
          return (
            <View key={b.key} style={{ marginTop: spacing.md }}>
              <Text
                style={{
                  fontFamily: fonts.mono,
                  fontSize: 11,
                  color: colors.textMuted,
                  textTransform: "uppercase",
                  letterSpacing: 1.2,
                }}
              >
                {b.label}
              </Text>

              {doBloco.map((r) => {
                const on = !!checks[r.slug];
                return (
                  <Pressable
                    key={r.slug}
                    onPress={() =>
                      setChecks((current) => ({
                        ...current,
                        [r.slug]: !current[r.slug],
                      }))
                    }
                    style={{ paddingVertical: 8 }}
                  >
                    <Text style={{ color: on ? colors.primary : colors.textMuted }}>
                      {on ? "☑" : "☐"} {r.nome}
                    </Text>

                    {r.passos.length > 0 && (
                      <View style={{ marginTop: 4, marginLeft: 20 }}>
                        {r.passos.map((p, i) => (
                          <Text
                            key={`${r.slug}-${i}`}
                            style={{
                              color: colors.textMuted,
                              fontFamily: fonts.ui,
                              fontSize: 12.5,
                              lineHeight: 18,
                            }}
                          >
                            {i + 1}. {p}
                          </Text>
                        ))}
                      </View>
                    )}
                  </Pressable>
                );
              })}
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
          <Text style={{ color: colors.textMuted, marginTop: 16 }}>
            como foi o dia?
          </Text>
          <TextInput
            multiline
            value={dump}
            onChangeText={setDump}
            placeholder="despeja aqui — 1 linha já vale"
            placeholderTextColor={colors.textMuted}
            style={{
              minHeight: 120,
              color: colors.text,
              backgroundColor: colors.card,
              borderRadius: 8,
              padding: 12,
              marginTop: 8,
            }}
          />
          <Pressable
            onPress={gerar}
            disabled={dumpActionsDisabled}
            style={{ marginTop: 12 }}
          >
            {busy ? (
              <ActivityIndicator />
            ) : (
              <Text
                style={{
                  color: colors.primary,
                  opacity: dumpActionsDisabled ? 0.45 : 1,
                }}
              >
                estruturar com o Hermes →
              </Text>
            )}
          </Pressable>
          <Pressable
            onPress={() => aprovar(dump)}
            disabled={dumpActionsDisabled}
            style={{ marginTop: 8 }}
          >
            <Text
              style={{
                color: colors.textMuted,
                opacity: dumpActionsDisabled ? 0.45 : 1,
              }}
            >
              gravar direto (modo mínimo)
            </Text>
          </Pressable>
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
              borderRadius: 8,
              padding: 12,
              marginTop: 8,
            }}
          />
          <Pressable
            onPress={() => aprovar(draft)}
            disabled={busy}
            style={{ marginTop: 12 }}
          >
            {busy ? (
              <ActivityIndicator />
            ) : (
              <Text style={{ color: colors.primary }}>
                aprovar e gravar ✓
              </Text>
            )}
          </Pressable>
          <Pressable
            onPress={() => setDraft(null)}
            disabled={busy}
            style={{ marginTop: 8 }}
          >
            <Text style={{ color: colors.textMuted }}>
              ← voltar ao despejo
            </Text>
          </Pressable>
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
