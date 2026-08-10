import Feather from "@expo/vector-icons/Feather";
import { useCallback, useEffect, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";

import { Agenda as AgendaData, EstadoFonteCalendario, getAgenda } from "../api";
import { faixaDeDias, rotuloDoDia } from "../agendaDias";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { Card, ErrorState, Skeleton } from "../ui";

// A agenda existia no servidor (GET /agenda, com ?data=) e NENHUMA tela chamava: dava
// pra ver só o dia de hoje, num card dentro da Abertura. Aqui a semana inteira fica a
// um toque — que é o mínimo pra decidir quando encaixar alguma coisa.
//
// O estado das fontes é mostrado de propósito: o BFF já degrada explicitamente
// ("cache", "erro", "nao_configurado") e esconder isso faria a agenda mentir por
// omissão — uma fonte fora do ar pareceria "dia livre".
const ESTADO_FONTE: Record<EstadoFonteCalendario, { texto: string; cor: string }> = {
  ok: { texto: "ao vivo", cor: colors.success },
  cache: { texto: "em cache", cor: colors.amber },
  erro: { texto: "indisponível", cor: colors.danger },
  nao_configurado: { texto: "não configurado", cor: colors.textMuted },
};

export default function Agenda() {
  const dias = faixaDeDias();
  const [selecionado, setSelecionado] = useState(dias[0].data);
  const [data, setData] = useState<AgendaData | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);

  const load = useCallback(async (dia: string) => {
    setLoading(true);
    try {
      setData(await getAgenda(dia));
      setErro(false);
    } catch {
      setErro(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(selecionado);
  }, [load, selecionado]);

  const eventos = data?.eventos ?? [];
  const tarefas = data?.tarefas_due ?? [];
  const vazio = !loading && eventos.length === 0 && tarefas.length === 0;

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={false} onRefresh={() => load(selecionado)} tintColor={colors.primary} />
      }
    >
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.faixa}>
        {dias.map((dia) => {
          const ativo = dia.data === selecionado;
          return (
            <Pressable
              key={dia.data}
              onPress={() => setSelecionado(dia.data)}
              style={[styles.dia, ativo && styles.diaAtivo]}
            >
              <Text style={[styles.diaRotulo, ativo && styles.diaRotuloAtivo]}>{dia.rotulo}</Text>
              <Text style={[styles.diaNumero, ativo && styles.diaNumeroAtivo]}>{dia.diaDoMes}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <Text style={styles.titulo}>{rotuloDoDia(selecionado)}</Text>

      {loading ? (
        <>
          <Skeleton height={64} />
          <Skeleton height={64} />
        </>
      ) : erro ? (
        <ErrorState
          message="Não consegui carregar a agenda."
          hint="O BFF está acessível? Toque pra tentar de novo."
          onRetry={() => load(selecionado)}
        />
      ) : (
        <>
          {eventos.map((evento, i) => (
            <View key={`${evento.titulo}-${i}`} style={styles.linha}>
              <Text style={styles.hora}>{evento.hora ?? "dia"}</Text>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={styles.eventoTitulo} numberOfLines={2}>{evento.titulo}</Text>
                <Text style={styles.fonte}>{evento.fonte}</Text>
              </View>
            </View>
          ))}

          {tarefas.length > 0 ? (
            <>
              <Text style={styles.secao}>VENCE NESTE DIA</Text>
              {tarefas.map((t) => (
                <View key={t.id} style={[styles.linha, { borderLeftColor: areaColor(t.area), borderLeftWidth: 3 }]}>
                  <Feather name="check-square" size={14} color={areaColor(t.area)} />
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={styles.eventoTitulo} numberOfLines={2}>{t.name}</Text>
                    <Text style={styles.fonte}>{t.area}</Text>
                  </View>
                </View>
              ))}
            </>
          ) : null}

          {vazio ? (
            <Card style={styles.vazio}>
              <Text style={styles.vazioTexto}>nada marcado neste dia.</Text>
            </Card>
          ) : null}
        </>
      )}

      {data?.fontes ? (
        <View style={styles.fontes}>
          {Object.entries(data.fontes).map(([nome, estado]) => {
            const info = ESTADO_FONTE[estado] ?? ESTADO_FONTE.nao_configurado;
            return (
              <View key={nome} style={styles.fonteChip}>
                <View style={[styles.fonteDot, { backgroundColor: info.cor }]} />
                <Text style={styles.fonteChipTexto}>{nome} · {info.texto}</Text>
              </View>
            );
          })}
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md, paddingBottom: spacing.xl, gap: spacing.sm },
  faixa: { gap: spacing.xs, paddingBottom: spacing.sm },
  dia: {
    minWidth: 56,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    gap: 2,
  },
  diaAtivo: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  diaRotulo: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, textTransform: "uppercase" },
  diaRotuloAtivo: { color: colors.primary },
  diaNumero: { fontFamily: fonts.mono, fontSize: 18, color: colors.textMuted },
  diaNumeroAtivo: { color: colors.text },
  titulo: { fontFamily: fonts.display, fontSize: 20, color: colors.text, marginTop: spacing.xs },
  secao: {
    fontFamily: fonts.mono,
    fontSize: 9.5,
    letterSpacing: 1.2,
    color: colors.textMuted,
    marginTop: spacing.md,
  },
  linha: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  hora: { fontFamily: fonts.mono, fontSize: 12, color: colors.primary, minWidth: 42 },
  eventoTitulo: { fontFamily: fonts.uiSemi, fontSize: 14.5, color: colors.text },
  fonte: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, marginTop: 2 },
  vazio: { alignItems: "center", paddingVertical: spacing.lg },
  vazioTexto: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted },
  fontes: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.lg },
  fonteChip: { flexDirection: "row", alignItems: "center", gap: 5 },
  fonteDot: { width: 6, height: 6, borderRadius: 3 },
  fonteChipTexto: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted },
});
