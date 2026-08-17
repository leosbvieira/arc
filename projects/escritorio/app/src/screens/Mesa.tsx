import Feather from "@expo/vector-icons/Feather";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AppState,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { Abertura, Shutdown, getAbertura, getShutdown, listAnkiCards } from "../api";
import { listPendingReadingSessions } from "../readingApi";
import { MesaSinais, montarMesa } from "../mesaView";
import { POINTS, colors, fonts, radius, spacing } from "../theme";
import { PendRow, Skeleton } from "../ui";

// Ícone e cor por destino — herdados da grade "Ferramentas" que saiu da Home.
// A Mesa herda o mapa, não reinventa. É a única cor da tela (o PendRow recebe
// por prop).
const VISUAL: Record<string, { icon: string; color: string }> = {
  agenda: { icon: "calendar", color: colors.info },
  abertura: { icon: "sunrise", color: colors.lilac },
  triagem: { icon: "inbox", color: colors.amber },
  rotinas: { icon: "repeat", color: colors.success },
  habitos: { icon: "trending-down", color: colors.info },
  revisao: { icon: "compass", color: colors.primary },
  edificacao: { icon: "layers", color: colors.lilac },
  melhorias: { icon: "zap", color: colors.amber },
  shutdown: { icon: "sunset", color: colors.primary },
  fechar: { icon: "moon", color: colors.info },
  settings: { icon: "settings", color: colors.textMuted },
  leitura: { icon: "book-open", color: colors.primary },
};

const FALLBACK_VISUAL = { icon: "circle", color: colors.textMuted };

export default function Mesa({ onOpenTab }: { onOpenTab?: (tab: string) => void }) {
  const [anki, setAnki] = useState<number | null>(null);
  const [leituras, setLeituras] = useState<number | null>(null);
  const [abertura, setAbertura] = useState<Abertura | null>(null);
  const [shutdown, setShutdown] = useState<Shutdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loaded, setLoaded] = useState<Set<string>>(new Set());
  const [failures, setFailures] = useState<Set<string>>(new Set());
  const loadEpoch = useRef(0);

  // Mesmo padrão da Home: timeout de 6s por chamada, loaded/failures em Set,
  // RefreshControl, recarga no AppState "active". Falha parcial não derruba a
  // tela — cada chamada que falha vira null no MesaSinais e o item cai no
  // arquivo em vez de mentir um estado.
  const load = useCallback(async (refresh = false) => {
    const epoch = ++loadEpoch.current;
    refresh ? setRefreshing(true) : setLoading(true);
    setFailures(new Set());

    const within = <T,>(promise: Promise<T>): Promise<T> =>
      Promise.race([
        promise,
        new Promise<T>((_, reject) => setTimeout(() => reject(new Error("timeout")), 6000)),
      ]);
    const run = async <T,>(key: string, promise: Promise<T>, apply: (value: T) => void) => {
      try {
        const value = await within(promise);
        if (loadEpoch.current !== epoch) return;
        apply(value);
        setLoaded((current) => new Set(current).add(key));
      } catch {
        if (loadEpoch.current !== epoch) return;
        setFailures((current) => new Set(current).add(key));
      }
    };

    // A contagem do Staging NÃO vem de `/triagem`. Aquele endpoint roda o Hermes
    // para propor destino item a item (11,6s medidos em 09/ago) e a Mesa usava
    // dele um número só — que o `/shutdown` já devolve em `staging.n`, na mesma
    // chamada de onde já vinha o `mais_velho_d`. Com o timeout de 6s daqui, a
    // chamada estourava SEMPRE: a Mesa esperava 6s fixos, acendia a faixa de
    // "alguns dados não responderam" e jogava a Triagem no arquivo sem contador.
    await Promise.all([
      run("anki", listAnkiCards("sugerido"), (value) => setAnki(value.length)),
      run("leituras", listPendingReadingSessions(), (value) => setLeituras(value.sessions.length)),
      run("abertura", getAbertura(), setAbertura),
      run("shutdown", getShutdown(), setShutdown),
    ]);
    if (loadEpoch.current === epoch) {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") load(true);
    });
    return () => subscription.remove();
  }, [load]);

  const partial = failures.size > 0;

  // Contagem e idade do Staging vêm da MESMA chamada (`/shutdown`), então ou as
  // duas existem ou nenhuma existe — sem o meio-termo de antes, em que a idade
  // podia faltar com a contagem presente.
  const sinais: MesaSinais = {
    triagem: loaded.has("shutdown")
      ? {
          n: shutdown?.staging.n ?? 0,
          maisVelhoD: shutdown?.staging.mais_velho_d ?? null,
        }
      : null,
    anki: loaded.has("anki") ? anki : null,
    leituras: loaded.has("leituras") ? leituras : null,
    aberturaFeita: loaded.has("abertura") ? abertura?.checkin.feito ?? null : null,
    shutdownFeito: loaded.has("shutdown") ? shutdown?.feito ?? null : null,
    ritmos: loaded.has("abertura") && abertura
      ? { feitos: abertura.rotinas_manha.filter((r) => r.feito).length, total: abertura.rotinas_manha.length }
      : null,
  };
  const grupos = montarMesa(sinais, POINTS);

  return (
    <View style={styles.root}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={colors.primary} />}
      >
        <View style={styles.header}>
          <Text style={styles.eyebrow}>sistema</Text>
          <Text style={styles.title}>A Mesa</Text>
        </View>

        {partial ? (
          <Pressable onPress={() => load(true)} style={styles.partial}>
            <Feather name="cloud-off" size={12} color={colors.textMuted} />
            <Text style={styles.partialText}>alguns dados não responderam · atualizar</Text>
          </Pressable>
        ) : null}

        {loading ? (
          <>
            <Skeleton height={56} />
            <Skeleton height={56} />
            <Skeleton height={56} />
            <Skeleton height={56} />
          </>
        ) : grupos.map((grupo) => (
          <View key={grupo.titulo} style={styles.group}>
            {/* Régua de grupo aprovada na C: eyebrow mono, filete, contador. */}
            <View style={styles.groupHeader}>
              <Text style={styles.groupTitle}>{grupo.titulo}</Text>
              <View style={styles.groupRule} />
              <Text style={styles.groupCount}>{grupo.itens.length}</Text>
            </View>
            {grupo.itens.map((item) => {
              const visual = VISUAL[item.destino] ?? FALLBACK_VISUAL;
              return (
                <PendRow
                  key={item.destino}
                  icon={visual.icon as keyof typeof Feather.glyphMap}
                  color={visual.color}
                  nome={item.nome}
                  sub={item.sub}
                  contador={item.contador}
                  feito={item.feito}
                  idle={grupo.titulo === "ARQUIVO"}
                  onPress={() => onOpenTab?.(item.destino)}
                />
              );
            })}
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: 128 },
  header: { marginBottom: spacing.lg },
  eyebrow: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, textTransform: "uppercase", letterSpacing: 1.2 },
  title: { fontFamily: fonts.display, fontSize: 30, color: colors.text, letterSpacing: -0.35, marginTop: 4 },
  partial: { flexDirection: "row", alignItems: "center", gap: 7, marginBottom: spacing.md },
  partialText: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 11.5 },
  group: { marginBottom: spacing.xl },
  groupHeader: { flexDirection: "row", alignItems: "center", marginBottom: spacing.sm, marginHorizontal: 2 },
  groupTitle: { fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted, letterSpacing: 1.8, textTransform: "uppercase" },
  groupRule: { flex: 1, height: 1, backgroundColor: colors.border, marginHorizontal: 10 },
  groupCount: { fontFamily: fonts.mono, fontSize: 9, color: colors.faint, letterSpacing: 0.8 },
});
