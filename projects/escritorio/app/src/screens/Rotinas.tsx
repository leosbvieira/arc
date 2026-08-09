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
  Bloco,
  createRoutine,
  deleteRoutine,
  listRoutines,
  reorderRoutines,
  Rotina,
  RotinaInput,
  updateRoutine,
} from "../api";
import { colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, ErrorState, Field, Skeleton } from "../ui";

const BLOCOS: { key: Bloco; label: string; icon: string }[] = [
  { key: "manha", label: "Manhã", icon: "sunrise" },
  { key: "dia", label: "Dia", icon: "sun" },
  { key: "noite", label: "Noite", icon: "moon" },
];

const DIAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"] as const;

const TEMPLATES: { key: string; label: string }[] = [
  { key: "*", label: "ambos" },
  { key: "yoga", label: "só yoga" },
  { key: "corrida", label: "só corrida" },
];

// "*" ou os 7 dias marcados = todo dia. Fora isso, lista os dias escolhidos.
function selo(r: Rotina): string {
  const partes: string[] = [];

  const dias = r.dias.trim();
  if (dias === "*" || dias === "") {
    partes.push("todo dia");
  } else {
    const marcados = dias.split(",").map((d) => d.trim()).filter(Boolean);
    partes.push(marcados.length >= DIAS.length ? "todo dia" : marcados.join(", "));
  }

  const tpl = r.templates.trim();
  if (tpl && tpl !== "*") {
    const marcados = tpl.split(",").map((t) => t.trim()).filter(Boolean);
    if (marcados.length === 1) partes.push(`só dia ${marcados[0]}`);
  }

  return partes.join(" · ");
}

type Form = {
  id: number | null; // null = nova
  nome: string;
  bloco: Bloco;
  todoDia: boolean;
  dias: string[];
  templates: string;
  passos: string[];
};

function novaForm(bloco: Bloco = "manha"): Form {
  return {
    id: null,
    nome: "",
    bloco,
    todoDia: true,
    dias: [],
    templates: "*",
    passos: [],
  };
}

function formDe(r: Rotina): Form {
  const dias = r.dias.trim();
  const todoDia = dias === "*" || dias === "";
  return {
    id: r.id,
    nome: r.nome,
    bloco: r.bloco,
    todoDia,
    dias: todoDia ? [] : dias.split(",").map((d) => d.trim()).filter(Boolean),
    templates: r.templates.trim() || "*",
    passos: [...r.passos],
  };
}

function paraInput(f: Form): RotinaInput {
  const passos = f.passos.map((p) => p.trim()).filter(Boolean);
  return {
    nome: f.nome.trim(),
    bloco: f.bloco,
    dias: f.todoDia || f.dias.length === 0 ? "*" : DIAS.filter((d) => f.dias.includes(d)).join(","),
    templates: f.templates,
    passos,
  };
}

function mover<T>(list: T[], from: number, to: number): T[] {
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

export default function Rotinas() {
  const [rotinas, setRotinas] = useState<Rotina[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [form, setForm] = useState<Form | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [confirmando, setConfirmando] = useState<number | null>(null);
  const [erro, setErro] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRotinas(await listRoutines());
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

  async function salvar() {
    if (!form) return;
    const body = paraInput(form);
    if (!body.nome) return;
    setSalvando(true);
    setErro("");
    try {
      if (form.id === null) await createRoutine(body);
      else await updateRoutine(form.id, body);
      setForm(null);
      await load();
    } catch {
      setErro("não consegui salvar — tenta de novo");
    } finally {
      setSalvando(false);
    }
  }

  async function remover(id: number) {
    setConfirmando(null);
    setErro("");
    const antes = rotinas;
    setRotinas((cur) => cur.filter((r) => r.id !== id));
    try {
      await deleteRoutine(id);
    } catch {
      setRotinas(antes);
      setErro("não consegui remover — tenta de novo");
    }
  }

  // ↑↓ dentro do bloco: reordena local (otimista) e manda a ordem inteira do bloco.
  async function reordenar(bloco: Bloco, from: number, to: number) {
    const doBloco = rotinas.filter((r) => r.bloco === bloco);
    if (to < 0 || to >= doBloco.length) return;
    const movido = mover(doBloco, from, to);
    const ordens = movido.map((r, i) => ({ id: r.id, ordem: i }));
    const mapa = new Map(ordens.map((o) => [o.id, o.ordem]));

    const antes = rotinas;
    setRotinas((cur) =>
      [...cur]
        .map((r) => (mapa.has(r.id) ? { ...r, ordem: mapa.get(r.id) as number } : r))
        .sort((a, b) => {
          const ba = BLOCOS.findIndex((x) => x.key === a.bloco);
          const bb = BLOCOS.findIndex((x) => x.key === b.bloco);
          return ba === bb ? a.ordem - b.ordem : ba - bb;
        }),
    );
    setErro("");

    try {
      await reorderRoutines(ordens);
    } catch {
      setRotinas(antes);
      setErro("não consegui reordenar — tenta de novo");
    }
  }

  if (form) {
    return (
      <Editor
        form={form}
        onChange={setForm}
        onSave={salvar}
        onCancel={() => {
          setForm(null);
          setErro("");
        }}
        salvando={salvando}
        erro={erro}
      />
    );
  }

  if (loading) {
    return (
      <View style={{ marginTop: spacing.md }}>
        <Skeleton height={14} style={{ width: 84, marginLeft: 2 }} />
        <Skeleton height={78} />
        <Skeleton height={78} />
        <Skeleton height={14} style={{ width: 84, marginLeft: 2, marginTop: spacing.md }} />
        <Skeleton height={78} />
      </View>
    );
  }

  if (error) {
    return (
      <ErrorState
        message="Não consegui carregar as rotinas."
        hint="O BFF (backend) está rodando na rede? Toque pra tentar de novo."
        onRetry={load}
      />
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingTop: spacing.sm, paddingBottom: spacing.xxl }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.intro}>
          As rotinas que já estão aqui são <Text style={styles.introHi}>só semente</Text>. Renomeia,
          reordena, joga fora e escreve as tuas — os passos são roteiro (pra não pular produto), quem
          conta no fechamento é o item.
        </Text>

        {!!erro && <Text style={styles.erro}>{erro}</Text>}

        {rotinas.length === 0 ? (
          <View style={styles.emptyWrap}>
            <Feather name="feather" size={28} color={colors.primary} />
            <Text style={styles.emptyTitle}>nenhuma rotina ainda</Text>
            <Text style={styles.emptyHint}>
              Começa pela primeira — acordar, skincare, pesagem, diário. Você decide o que conta.
            </Text>
          </View>
        ) : (
          BLOCOS.map((b) => {
            const doBloco = rotinas.filter((r) => r.bloco === b.key);
            if (doBloco.length === 0) return null;
            return (
              <View key={b.key} style={{ marginBottom: spacing.lg }}>
                <View style={styles.blocoHead}>
                  <Feather name={b.icon as any} size={13} color={colors.textMuted} />
                  <Text style={styles.blocoLabel}>{b.label}</Text>
                </View>

                {doBloco.map((r, i) => (
                  <View key={r.id} style={styles.item}>
                    <View style={styles.itemTop}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.itemNome}>{r.nome}</Text>
                        <View style={styles.seloRow}>
                          <Text style={styles.selo}>{selo(r)}</Text>
                          {r.origem === "exemplo" && (
                            <Text style={styles.exemplo}>exemplo</Text>
                          )}
                        </View>
                      </View>

                      <View style={styles.acoes}>
                        <IconBtn
                          icon="chevron-up"
                          disabled={i === 0}
                          onPress={() => reordenar(b.key, i, i - 1)}
                        />
                        <IconBtn
                          icon="chevron-down"
                          disabled={i === doBloco.length - 1}
                          onPress={() => reordenar(b.key, i, i + 1)}
                        />
                        <IconBtn icon="edit-2" onPress={() => setForm(formDe(r))} />
                        <IconBtn
                          icon="trash-2"
                          tint={colors.danger}
                          onPress={() => setConfirmando(r.id)}
                        />
                      </View>
                    </View>

                    {r.passos.length > 0 && (
                      <View style={styles.passos}>
                        {r.passos.map((p, idx) => (
                          <Text key={`${r.id}-${idx}`} style={styles.passo}>
                            <Text style={styles.passoNum}>{idx + 1}. </Text>
                            {p}
                          </Text>
                        ))}
                      </View>
                    )}

                    {confirmando === r.id && (
                      <View style={styles.confirm}>
                        <Text style={styles.confirmText}>remover “{r.nome}”?</Text>
                        <Pressable onPress={() => remover(r.id)} hitSlop={6}>
                          <Text style={styles.confirmSim}>remover</Text>
                        </Pressable>
                        <Pressable onPress={() => setConfirmando(null)} hitSlop={6}>
                          <Text style={styles.confirmNao}>cancelar</Text>
                        </Pressable>
                      </View>
                    )}
                  </View>
                ))}
              </View>
            );
          })
        )}
      </ScrollView>

      <View style={styles.dock}>
        <AppButton title="+ Nova rotina" onPress={() => setForm(novaForm())} />
      </View>
    </View>
  );
}

function IconBtn({
  icon,
  onPress,
  disabled,
  tint,
}: {
  icon: string;
  onPress: () => void;
  disabled?: boolean;
  tint?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      hitSlop={4}
      style={({ pressed }) => [
        styles.iconBtn,
        disabled && { opacity: 0.25 },
        pressed && !disabled && { opacity: 0.6 },
      ]}
    >
      <Feather name={icon as any} size={15} color={tint ?? colors.textMuted} />
    </Pressable>
  );
}

function Editor({
  form,
  onChange,
  onSave,
  onCancel,
  salvando,
  erro,
}: {
  form: Form;
  onChange: (f: Form) => void;
  onSave: () => void;
  onCancel: () => void;
  salvando: boolean;
  erro: string;
}) {
  const set = (patch: Partial<Form>) => onChange({ ...form, ...patch });

  const toggleDia = (d: string) =>
    set({
      dias: form.dias.includes(d) ? form.dias.filter((x) => x !== d) : [...form.dias, d],
    });

  const setPasso = (i: number, v: string) =>
    set({ passos: form.passos.map((p, idx) => (idx === i ? v : p)) });

  const removePasso = (i: number) => set({ passos: form.passos.filter((_, idx) => idx !== i) });

  const movePasso = (i: number, to: number) => set({ passos: mover(form.passos, i, to) });

  const podeSalvar = !!form.nome.trim() && !salvando;

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingTop: spacing.sm, paddingBottom: spacing.xxl }}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
    >
      <Card style={{ gap: spacing.md }}>
        <Text style={styles.editorTitle}>
          {form.id === null ? "Nova rotina" : "Editar rotina"}
        </Text>

        <View style={{ gap: spacing.sm }}>
          <Text style={styles.label}>NOME</Text>
          <Field
            value={form.nome}
            onChangeText={(nome) => set({ nome })}
            placeholder="ex.: skincare da noite"
          />
        </View>

        <View style={{ gap: spacing.sm }}>
          <Text style={styles.label}>QUANDO</Text>
          <View style={styles.pills}>
            {BLOCOS.map((b) => {
              const on = b.key === form.bloco;
              return (
                <Pressable
                  key={b.key}
                  onPress={() => set({ bloco: b.key })}
                  style={[styles.pill, on && styles.pillOn]}
                >
                  <Text style={[styles.pillText, on && styles.pillTextOn]}>{b.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={{ gap: spacing.sm }}>
          <Text style={styles.label}>DIAS</Text>
          <View style={styles.pills}>
            <Pressable
              onPress={() => set({ todoDia: true, dias: [] })}
              style={[styles.pill, form.todoDia && styles.pillOn]}
            >
              <Text style={[styles.pillText, form.todoDia && styles.pillTextOn]}>todo dia</Text>
            </Pressable>
            <Pressable
              onPress={() => set({ todoDia: false })}
              style={[styles.pill, !form.todoDia && styles.pillOn]}
            >
              <Text style={[styles.pillText, !form.todoDia && styles.pillTextOn]}>
                dias escolhidos
              </Text>
            </Pressable>
          </View>

          {!form.todoDia && (
            <View style={styles.pills}>
              {DIAS.map((d) => {
                const on = form.dias.includes(d);
                return (
                  <Pressable
                    key={d}
                    onPress={() => toggleDia(d)}
                    style={[styles.dia, on && styles.pillOn]}
                  >
                    <Text style={[styles.pillText, on && styles.pillTextOn]}>{d}</Text>
                  </Pressable>
                );
              })}
            </View>
          )}
          {!form.todoDia && form.dias.length === 0 && (
            <Text style={styles.hint}>nenhum dia marcado = vale todo dia</Text>
          )}
        </View>

        <View style={{ gap: spacing.sm }}>
          <Text style={styles.label}>TEMPLATE</Text>
          <View style={styles.pills}>
            {TEMPLATES.map((t) => {
              const on = t.key === form.templates;
              return (
                <Pressable
                  key={t.key}
                  onPress={() => set({ templates: t.key })}
                  style={[styles.pill, on && styles.pillOn]}
                >
                  <Text style={[styles.pillText, on && styles.pillTextOn]}>{t.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={{ gap: spacing.sm }}>
          <Text style={styles.label}>PASSOS (ROTEIRO — NÃO CONTAM NO PLACAR)</Text>
          {form.passos.length === 0 ? (
            <Text style={styles.hint}>
              sem passos. Use pra ordem dos produtos, por exemplo — o check continua sendo só um.
            </Text>
          ) : (
            form.passos.map((p, i) => (
              <View key={i} style={styles.passoRow}>
                <Text style={styles.passoRowNum}>{i + 1}</Text>
                <Field
                  value={p}
                  onChangeText={(v) => setPasso(i, v)}
                  placeholder={`passo ${i + 1}`}
                  style={{ flex: 1 }}
                />
                <IconBtn icon="chevron-up" disabled={i === 0} onPress={() => movePasso(i, i - 1)} />
                <IconBtn
                  icon="chevron-down"
                  disabled={i === form.passos.length - 1}
                  onPress={() => movePasso(i, i + 1)}
                />
                <IconBtn icon="x" tint={colors.danger} onPress={() => removePasso(i)} />
              </View>
            ))
          )}
          <Pressable
            onPress={() => set({ passos: [...form.passos, ""] })}
            style={styles.addPasso}
            hitSlop={6}
          >
            <Feather name="plus" size={14} color={colors.primary} />
            <Text style={styles.addPassoText}>adicionar passo</Text>
          </Pressable>
        </View>

        {!!erro && <Text style={styles.erro}>{erro}</Text>}

        <AppButton
          title={form.id === null ? "Criar rotina" : "Salvar"}
          onPress={onSave}
          loading={salvando}
          disabled={!podeSalvar}
        />
        <AppButton title="Cancelar" variant="ghost" onPress={onCancel} disabled={salvando} />
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  intro: {
    fontFamily: fonts.ui,
    fontSize: 13,
    lineHeight: 19,
    color: colors.textMuted,
    marginBottom: spacing.lg,
  },
  introHi: { color: colors.primary, fontFamily: fonts.uiSemi },
  erro: { fontFamily: fonts.ui, fontSize: 13, color: colors.danger, marginBottom: spacing.sm },

  blocoHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  blocoLabel: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 1.2,
  },

  item: {
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  itemTop: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  itemNome: { fontFamily: fonts.uiSemi, fontSize: 15.5, color: colors.text },
  seloRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: 3 },
  selo: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted },
  exemplo: {
    fontFamily: fonts.mono,
    fontSize: 9.5,
    color: colors.textMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: 7,
    paddingVertical: 1,
    textTransform: "uppercase",
    letterSpacing: 0.8,
  },
  acoes: { flexDirection: "row", alignItems: "center", gap: 2 },
  iconBtn: { width: 28, height: 28, alignItems: "center", justifyContent: "center" },

  passos: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 2,
  },
  passo: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, lineHeight: 18 },
  passoNum: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted },

  confirm: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  confirmText: { flex: 1, fontFamily: fonts.ui, fontSize: 13, color: colors.text },
  confirmSim: { fontFamily: fonts.uiSemi, fontSize: 13, color: colors.danger },
  confirmNao: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },

  emptyWrap: {
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.card2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
  },
  emptyTitle: { fontFamily: fonts.uiSemi, fontSize: 17, color: colors.text },
  emptyHint: {
    fontFamily: fonts.ui,
    fontSize: 13,
    color: colors.textMuted,
    textAlign: "center",
    lineHeight: 19,
  },

  dock: { paddingVertical: spacing.md },

  editorTitle: { fontFamily: fonts.uiSemi, fontSize: 20, color: colors.text },
  label: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted, letterSpacing: 1 },
  hint: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, lineHeight: 18 },
  pills: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  pill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  dia: {
    minWidth: 44,
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  pillOn: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  pillText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  pillTextOn: { color: colors.primary, fontFamily: fonts.uiSemi },

  passoRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  passoRowNum: {
    width: 16,
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textMuted,
  },
  addPasso: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    alignSelf: "flex-start",
    paddingVertical: 6,
  },
  addPassoText: { fontFamily: fonts.uiSemi, fontSize: 13, color: colors.primary },
});
