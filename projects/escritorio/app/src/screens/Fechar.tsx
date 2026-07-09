import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { closingApprove, closingDraft, closingRoutines } from "../api";
import { colors } from "../theme";

export default function Fechar() {
  const [template, setTemplate] = useState<"yoga" | "corrida">("yoga");
  const [routines, setRoutines] = useState<string[]>([]);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [dump, setDump] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    closingRoutines(template).then((rs) => {
      setRoutines(rs);
      setChecks(Object.fromEntries(rs.map((r) => [r, false])));
    }).catch(() => setErr("sem conexão com o BFF"));
  }, [template]);

  const gerar = async () => {
    setBusy(true); setErr("");
    try { setDraft(await closingDraft(dump, template)); }
    catch { setErr("não consegui estruturar — tenta de novo ou grava direto"); }
    finally { setBusy(false); }
  };

  const aprovar = async (md: string) => {
    setBusy(true); setErr("");
    try {
      await closingApprove({ raw_text: dump, draft_md: md, template,
        checks: routines.map((r) => ({ rotina: r, feito: !!checks[r] })) });
      setDone(true);
    } catch { setErr("falha ao gravar — nada se perdeu, tenta de novo"); }
    finally { setBusy(false); }
  };

  if (done) return <View style={{ padding: 24 }}><Text style={{ color: colors.text, fontSize: 18 }}>✓ dia fechado</Text></View>;

  return (
    <ScrollView style={{ flex: 1, padding: 16 }}>
      <View style={{ flexDirection: "row", gap: 8 }}>
        {(["yoga", "corrida"] as const).map((t) => (
          <Pressable key={t} onPress={() => setTemplate(t)}
            style={{ padding: 8, borderRadius: 8, backgroundColor: template === t ? colors.primary : colors.card }}>
            <Text style={{ color: colors.text }}>dia {t}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={{ color: colors.textMuted, marginTop: 16 }}>rotinas de hoje</Text>
      {routines.map((r) => (
        <Pressable key={r} onPress={() => setChecks({ ...checks, [r]: !checks[r] })}
          style={{ flexDirection: "row", paddingVertical: 8 }}>
          <Text style={{ color: checks[r] ? colors.primary : colors.textMuted }}>{checks[r] ? "☑" : "☐"} {r}</Text>
        </Pressable>
      ))}

      {draft === null ? (
        <>
          <Text style={{ color: colors.textMuted, marginTop: 16 }}>como foi o dia?</Text>
          <TextInput multiline value={dump} onChangeText={setDump}
            placeholder="despeja aqui — 1 linha já vale"
            placeholderTextColor={colors.textMuted}
            style={{ minHeight: 120, color: colors.text, backgroundColor: colors.card, borderRadius: 8, padding: 12, marginTop: 8 }} />
          <Pressable onPress={gerar} disabled={busy || !dump.trim()} style={{ marginTop: 12 }}>
            {busy ? <ActivityIndicator /> : <Text style={{ color: colors.primary }}>estruturar com o Hermes →</Text>}
          </Pressable>
          <Pressable onPress={() => aprovar(dump)} disabled={busy || !dump.trim()} style={{ marginTop: 8 }}>
            <Text style={{ color: colors.textMuted }}>gravar direto (modo mínimo)</Text>
          </Pressable>
        </>
      ) : (
        <>
          <Text style={{ color: colors.textMuted, marginTop: 16 }}>rascunho — edita à vontade, gravo exatamente isto</Text>
          <TextInput multiline value={draft} onChangeText={setDraft}
            style={{ minHeight: 200, color: colors.text, backgroundColor: colors.card, borderRadius: 8, padding: 12, marginTop: 8 }} />
          <Pressable onPress={() => aprovar(draft)} disabled={busy} style={{ marginTop: 12 }}>
            {busy ? <ActivityIndicator /> : <Text style={{ color: colors.primary }}>aprovar e gravar ✓</Text>}
          </Pressable>
          <Pressable onPress={() => setDraft(null)} disabled={busy} style={{ marginTop: 8 }}>
            <Text style={{ color: colors.textMuted }}>← voltar ao despejo</Text>
          </Pressable>
        </>
      )}
      {!!err && <Text style={{ color: colors.danger, marginTop: 12 }}>{err}</Text>}
    </ScrollView>
  );
}
