import Feather from "@expo/vector-icons/Feather";
import { ComponentProps, ReactNode, useEffect, useRef } from "react";
import {
  ActivityIndicator,
  Animated,
  Pressable,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  View,
  ViewStyle,
} from "react-native";

import type { Pontos } from "./api";
import { milhar } from "./format";
import { colors, fonts, radius, shadow, spacing } from "./theme";

export function Card({
  children,
  style,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function AppButton({
  title,
  onPress,
  disabled,
  loading,
  variant = "primary",
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "primary" | "ghost";
}) {
  const ghost = variant === "ghost";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.btn,
        ghost ? styles.btnGhost : styles.btnPrimary,
        (disabled || loading) && { opacity: 0.5 },
        pressed && { opacity: 0.85 },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={ghost ? colors.primary : colors.primaryText} />
      ) : (
        <Text style={[styles.btnText, ghost ? styles.btnTextGhost : styles.btnTextPrimary]}>
          {title}
        </Text>
      )}
    </Pressable>
  );
}

export function Field(props: TextInputProps) {
  return (
    <TextInput
      placeholderTextColor={colors.textMuted}
      {...props}
      style={[styles.field, props.style]}
    />
  );
}

export function SectionHeader({
  eyebrow,
  title,
  action,
  onAction,
  meta,
}: {
  eyebrow?: string;
  title: string;
  action?: string;
  onAction?: () => void;
  meta?: string;
}) {
  return (
    <View style={styles.sectionHeader}>
      <View style={{ flex: 1 }}>
        {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      {action && onAction ? (
        <Pressable accessibilityRole="button" accessibilityLabel={action} onPress={onAction} hitSlop={8}>
          <Text style={styles.sectionAction}>{action}</Text>
        </Pressable>
      ) : meta ? (
        // Fato, não botão: o slot da direita é um só e action vence.
        <Text style={styles.sectionMeta}>{meta}</Text>
      ) : null}
    </View>
  );
}

// Ponto de ação na lista (onda 3b). Em repouso é DATILOGRAFIA: mono miúdo,
// faint, largura fixa de 34 — é o que faz doze linhas virarem uma régua quieta
// em vez de uma serrilha. NUNCA pill, fundo, borda ou bronze (foi badge
// colorido que afundou a rodada D). Aceso (conclusão confirmada): sálvia,
// sobe 12px esmaecendo até 0 em 350ms — abaixo dos 400ms da lei.
export function PointTag({ pontos, aceso = false }: { pontos: number; aceso?: boolean }) {
  const rise = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!aceso) return;
    rise.setValue(0);
    Animated.timing(rise, { toValue: 1, duration: 350, useNativeDriver: true }).start();
  }, [aceso, rise]);
  return (
    <Animated.Text
      style={[
        styles.pointTag,
        aceso && {
          color: colors.success,
          opacity: rise.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }),
          transform: [{ translateY: rise.interpolate({ inputRange: [0, 1], outputRange: [0, -12] }) }],
        },
      ]}
    >
      +{pontos}
    </Animated.Text>
  );
}

// Chip de fila (decisão 07=C): moldura neutra, mono miúdo, ponto de 4px na cor
// da fila. O número vem ANTES do rótulo e na cor do texto — a única cor é o
// ponto. Nunca borda ou número coloridos (foi o badge colorido que afundou a D).
export function Badge({
  label,
  value,
  color = colors.primary,
}: {
  label: string;
  value?: string | number;
  color?: string;
}) {
  return (
    <View style={styles.badge}>
      <View style={[styles.badgeDot, { backgroundColor: color }]} />
      {value !== undefined ? <Text style={styles.badgeValue}>{value}</Text> : null}
      <Text style={styles.badgeLabel}>{label}</Text>
    </View>
  );
}

export function ProgressBar({
  value,
  color = colors.primary,
}: {
  value: number;
  color?: string;
}) {
  const width = `${Math.max(0, Math.min(1, value)) * 100}%` as `${number}%`;
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: 100, now: Math.round(Math.max(0, Math.min(1, value)) * 100) }}
      style={styles.progressTrack}
    >
      <View style={[styles.progressFill, { width, backgroundColor: color }]} />
    </View>
  );
}

export function IconButton({
  icon,
  onPress,
  color = colors.text,
  label,
}: {
  icon: ComponentProps<typeof Feather>["name"];
  onPress: () => void;
  color?: string;
  label: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [styles.iconButton, pressed && { opacity: 0.7 }]}
    >
      <Feather name={icon} size={18} color={color} />
    </Pressable>
  );
}

export function Skeleton({
  height = 64,
  style,
}: {
  height?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const op = useRef(new Animated.Value(0.4)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(op, { toValue: 0.85, duration: 750, useNativeDriver: true }),
        Animated.timing(op, { toValue: 0.4, duration: 750, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [op]);
  return <Animated.View style={[styles.skeleton, { height, opacity: op }, style]} />;
}

export function ErrorState({
  message,
  hint,
  onRetry,
}: {
  message: string;
  hint?: string;
  onRetry: () => void;
}) {
  return (
    <View style={styles.errWrap}>
      <Feather name="wifi-off" size={28} color={colors.textMuted} />
      <Text style={styles.errText}>{message}</Text>
      {hint ? <Text style={styles.errHint}>{hint}</Text> : null}
      <Pressable accessibilityRole="button" onPress={onRetry} style={styles.errBtn}>
        <Feather name="refresh-cw" size={14} color={colors.text} />
        <Text style={styles.errBtnText}>Tentar de novo</Text>
      </Pressable>
    </View>
  );
}

// ---- Onda 1 (C2 sóbria) ---------------------------------------------------
// Bronze-press do design (fio de 2px na base do primário). Token local enquanto
// o theme.ts não tem essa cor — a proposta não pediu token novo para ela.
const BRONZE_PRESS = "#B6935C";
const LINE_STRONG = "rgba(235,222,202,0.20)";
const SAGE_SOFT = "rgba(113,180,154,0.12)";
const SAGE_LINE = "rgba(113,180,154,0.45)";
const SEG_OFF = "rgba(235,222,202,0.09)";

// O ÚNICO bronze cheio da tela. Sempre habilitado, salvo erro real de carga —
// quem decide o bloqueio é a tela. Afunda 2px no toque (80ms, bem abaixo dos
// 400ms da lei). A exceção declarada de "um bronze por tela" é a RewardSheet.
export function BigAction({
  title,
  sub,
  onPress,
  disabled,
  loading,
  small,
}: {
  title: string;
  sub?: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  small?: boolean;
}) {
  const sink = useRef(new Animated.Value(0)).current;
  const sinkTo = (toValue: number) =>
    Animated.timing(sink, { toValue, duration: 80, useNativeDriver: true }).start();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      onPress={onPress}
      onPressIn={() => sinkTo(2)}
      onPressOut={() => sinkTo(0)}
      disabled={disabled || loading}
    >
      <Animated.View
        style={[
          styles.bigact,
          small && styles.bigactSmall,
          (disabled || loading) && { opacity: 0.5 },
          { transform: [{ translateY: sink }] },
        ]}
      >
        {loading ? (
          <ActivityIndicator color={colors.primaryText} />
        ) : (
          <>
            <Text style={[styles.bigactTitle, small && styles.bigactTitleSmall]}>{title}</Text>
            {sub ? (
              <Text style={styles.bigactSub} numberOfLines={1}>
                {sub}
              </Text>
            ) : null}
          </>
        )}
      </Animated.View>
    </Pressable>
  );
}

// Linha de rotina do rito. Pontos são METADADO: mono miúdo, faint, coluna à
// direita — nunca bronze, nunca pill, nunca fundo. Feito sobe um degrau para
// sálvia. Checkbox quadrado 24px, canto 7 (pedido explícito do Leo). Os passos
// são roteiro em mono, SEM check próprio — quem conta é o item pai, binário.
export function QuestRow({
  name,
  done,
  points,
  steps,
  onPress,
}: {
  name: string;
  done: boolean;
  points: number;
  steps?: string[];
  onPress: () => void;
}) {
  const pop = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (!done) return;
    pop.setValue(0.6);
    Animated.timing(pop, { toValue: 1, duration: 180, useNativeDriver: true }).start();
  }, [done, pop]);
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: done }}
      accessibilityLabel={name}
      onPress={onPress}
      style={({ pressed }) => [styles.quest, pressed && { opacity: 0.85 }]}
    >
      <Animated.View
        style={[styles.questBox, done && styles.questBoxDone, { transform: [{ scale: pop }] }]}
      >
        {done ? <Feather name="check" size={13} color={colors.success} /> : null}
      </Animated.View>
      <View style={{ flex: 1 }}>
        <Text style={[styles.questName, done && { color: colors.textMuted }]}>{name}</Text>
        {steps && steps.length > 0 ? (
          <Text style={styles.questSteps}>
            {steps.map((p, i) => `${i + 1}. ${p}`).join(" · ")}
          </Text>
        ) : null}
      </View>
      <Text style={[styles.questPts, done && { color: colors.success }]}>+{points}</Text>
    </Pressable>
  );
}

// Barra segmentada: bronze para ciclo, sálvia para "feito". Sem glow.
// outlineNext (decisão 09=C): o segmento seguinte aos cheios fica vazado com
// filete na cor do tom — o "vem agora" se lê sem encher barra que não encheu.
export function SegmentBar({
  value,
  segments = 10,
  tone = "bronze",
  outlineNext = false,
}: {
  value: number; // 0..1
  segments?: number;
  tone?: "bronze" | "sage";
  outlineNext?: boolean;
}) {
  const filled = Math.round(Math.max(0, Math.min(1, value)) * segments);
  const on = tone === "sage" ? colors.success : colors.primary;
  return (
    <View style={styles.seg}>
      {Array.from({ length: segments }, (_, i) => (
        <View
          key={i}
          style={[
            styles.segItem,
            { backgroundColor: i < filled ? on : SEG_OFF },
            outlineNext &&
              i === filled && {
                backgroundColor: "transparent",
                borderWidth: 1,
                borderColor: `${on}8C`,
              },
          ]}
        />
      ))}
    </View>
  );
}

// Linha da Mesa (onda 3a). Um número de trabalho parado à direita em mono, na
// cor do texto — SEM pill, sem fundo, sem accent: foi a pill colorida que o Leo
// rejeitou na variação C. A única cor é o ícone, que vem por prop. Estado feito
// troca o contador por "FEITO ✓" em sálvia. Na variante idle (arquivo) a linha
// inteira cai a ~50% de opacidade e o ícone perde a cor semântica.
export function PendRow({
  icon,
  color,
  nome,
  sub,
  contador,
  feito = false,
  idle = false,
  onPress,
}: {
  icon: ComponentProps<typeof Feather>["name"];
  color: string;
  nome: string;
  sub: string;
  contador: string | null;
  feito?: boolean;
  idle?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={nome}
      onPress={onPress}
      style={({ pressed }) => [styles.pend, idle && styles.pendIdle, pressed && { opacity: 0.85 }]}
    >
      <View style={[styles.pendIcon, { backgroundColor: `${idle ? colors.textMuted : color}19` }]}>
        <Feather name={icon} size={17} color={idle ? colors.textMuted : color} />
      </View>
      <View style={styles.pendBody}>
        <Text style={styles.pendName} numberOfLines={1}>{nome}</Text>
        <Text style={styles.pendSub} numberOfLines={1}>{sub}</Text>
      </View>
      {feito ? (
        <Text style={styles.pendFeito}>FEITO ✓</Text>
      ) : contador !== null ? (
        <Text style={styles.pendContador}>{contador}</Text>
      ) : null}
    </Pressable>
  );
}

// O fim do rito devolve o que ele produziu. Usa só o que getPontos() já traz
// (saldo, nível, ciclo) — SEM linha de streak: o BFF não expõe sequência
// corrida, e nenhum número se inventa. Pelo mesmo motivo o SALDO mostra só o
// valor atual: o "antes → depois" da decisão 10=C pede o saldo anterior, que o
// BFF não devolve. `pontosHoje` vem da tabela POINTS (provisória, display-only):
// é o número que o botão prometeu. Tipografia da onda 2 entregue: herói em
// display/Syne Bold, metadados em mono. O bronze do herói ficou só no "+" —
// os dígitos são cor do texto (decisão 10=C).
// Entra em fade + subida, 320ms.
export function RewardSheet({
  pontosHoje,
  placar,
  ritmosFeitos,
  ritmosTotal,
  onBoaNoite,
  onVerSemMarcar,
}: {
  pontosHoje: number;
  placar: Pontos | null;
  ritmosFeitos: number;
  ritmosTotal: number;
  onBoaNoite?: () => void;
  onVerSemMarcar?: () => void;
}) {
  const enter = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(enter, { toValue: 1, duration: 320, useNativeDriver: true }).start();
  }, [enter]);
  const animatedStyle = {
    opacity: enter,
    transform: [
      { translateY: enter.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) },
    ],
  };
  return (
    <Animated.View style={[styles.reward, animatedStyle]}>
      <Text style={styles.rewardCrumb}>dia fechado · registro gravado</Text>
      <Text style={styles.rewardHero}>
        <Text style={{ color: colors.primary }}>+</Text>
        {pontosHoje}
      </Text>
      <Text style={styles.rewardHeroLabel}>PONTOS DE HOJE</Text>

      {placar ? (
        <View style={styles.rewardCard}>
          <View style={styles.rewardRow}>
            <Text style={styles.rewardLabel}>SALDO</Text>
            <Text style={styles.rewardSaldo}>
              {milhar(placar.saldo_total)}
            </Text>
          </View>
          <View style={[styles.rewardRow, { marginTop: 13 }]}>
            <Text style={styles.rewardLabel}>NÍVEL {placar.nivel}</Text>
            <View style={styles.diams}>
              {[1, 2, 3, 4].map((n) => (
                <View key={n} style={[styles.diam, placar.nivel >= n && styles.diamOn]} />
              ))}
            </View>
          </View>
          <View style={{ marginTop: 12 }}>
            <SegmentBar
              value={placar.ciclo.meta > 0 ? placar.ciclo.pontos / placar.ciclo.meta : 0}
              segments={10}
            />
            <View style={styles.rewardCycleFoot}>
              <Text style={styles.rewardCycleLeft}>
                ciclo {placar.ciclo.indice} · semana {placar.ciclo.semana}/{placar.ciclo.de}
              </Text>
              {placar.proximo_nivel ? (
                <Text style={styles.rewardCycleRight}>
                  faltam {placar.proximo_nivel.faltam} p/ N{placar.proximo_nivel.n}
                </Text>
              ) : null}
            </View>
          </View>
        </View>
      ) : null}

      {ritmosTotal > 0 ? (
        <View style={[styles.rewardCard, { marginTop: 10 }]}>
          <View style={styles.rewardRow}>
            <Text style={styles.rewardLabel}>RITMOS</Text>
            <Text style={styles.rewardSaldo}>
              {ritmosFeitos}
              <Text style={styles.rewardSaldoSmall}>/{ritmosTotal}</Text>
            </Text>
          </View>
          <View style={{ marginTop: 10 }}>
            <SegmentBar
              value={ritmosFeitos / ritmosTotal}
              segments={Math.min(ritmosTotal, 12)}
              tone="sage"
            />
          </View>
        </View>
      ) : null}

      {/* Saída de um toque (decisão 10=C): antes o dia fechado não devolvia
          caminho — só tabbar ou gesto. O bronze do BigAction é a exceção
          declarada de "um bronze por tela", já citada no cabeçalho dele. */}
      {onBoaNoite ? (
        <View style={{ marginTop: 24 }}>
          <BigAction title="Boa noite" onPress={onBoaNoite} />
        </View>
      ) : null}
      {onVerSemMarcar ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="ver o que ficou sem marcar"
          onPress={onVerSemMarcar}
          style={({ pressed }) => [styles.rewardGhost, pressed && { opacity: 0.7 }]}
        >
          <Text style={styles.rewardGhostText}>ver o que ficou sem marcar</Text>
        </Pressable>
      ) : null}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadow,
  },
  btn: {
    height: 50,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  btnPrimary: { backgroundColor: colors.primary },
  btnGhost: { backgroundColor: "transparent", borderWidth: 1, borderColor: colors.border },
  btnText: { fontSize: 16, fontFamily: fonts.uiSemi },
  btnTextPrimary: { color: colors.primaryText },
  btnTextGhost: { color: colors.text },
  field: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: 16,
    fontFamily: fonts.ui,
    color: colors.text,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  eyebrow: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.primary,
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginBottom: 4,
  },
  sectionTitle: {
    fontFamily: fonts.uiSemi,
    fontSize: 21,
    color: colors.text,
    letterSpacing: -0.3,
  },
  sectionAction: { fontFamily: fonts.uiSemi, color: colors.primary, fontSize: 12 },
  sectionMeta: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.faint },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    minHeight: 32,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: 12,
  },
  badgeDot: { width: 4, height: 4, borderRadius: 2 },
  badgeLabel: { fontFamily: fonts.mono, fontSize: 10, color: colors.textMuted, letterSpacing: 0.3 },
  badgeValue: { fontFamily: fonts.mono, fontSize: 10, color: colors.text },
  progressTrack: {
    height: 5,
    borderRadius: radius.pill,
    backgroundColor: "rgba(255,255,255,0.07)",
    overflow: "hidden",
  },
  progressFill: { height: "100%", borderRadius: radius.pill },
  iconButton: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card2,
  },
  skeleton: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
  errWrap: { alignItems: "center", justifyContent: "center", paddingVertical: 48, gap: spacing.sm },
  errText: { fontFamily: fonts.uiSemi, fontSize: 15, color: colors.text, textAlign: "center" },
  errHint: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted, textAlign: "center", paddingHorizontal: spacing.xl },
  errBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: 16,
    paddingVertical: 9,
  },
  errBtnText: { fontFamily: fonts.uiSemi, fontSize: 13, color: colors.text },
  bigact: {
    minHeight: 60,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    paddingHorizontal: 18,
    backgroundColor: colors.primary,
    borderRadius: 14,
    borderBottomWidth: 2,
    borderBottomColor: BRONZE_PRESS,
  },
  bigactSmall: { minHeight: 46 },
  bigactTitle: { fontFamily: fonts.uiSemi, fontSize: 15.5, color: colors.primaryText },
  bigactTitleSmall: { fontSize: 13.5 },
  bigactSub: {
    fontFamily: fonts.mono,
    fontSize: 10.5,
    letterSpacing: 0.4,
    color: colors.primaryText,
    opacity: 0.72,
    // No Yoga o padrão de flex-shrink é 0 (na web é 1): sem isto o sub não
    // encolhe e vaza para fora do botão num aparelho de 360dp.
    flexShrink: 1,
  },
  quest: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
  questBox: {
    width: 24,
    height: 24,
    borderRadius: 7,
    borderWidth: 1.5,
    borderColor: LINE_STRONG,
    backgroundColor: colors.card2,
    alignItems: "center",
    justifyContent: "center",
  },
  questBoxDone: { backgroundColor: SAGE_SOFT, borderColor: SAGE_LINE },
  questName: { fontFamily: fonts.ui, fontSize: 14, color: colors.text, lineHeight: 18 },
  questSteps: {
    fontFamily: fonts.mono,
    fontSize: 9,
    color: colors.faint,
    letterSpacing: 0.3,
    marginTop: 3,
  },
  questPts: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.faint,
    letterSpacing: 0.3,
    minWidth: 30,
    textAlign: "right",
  },
  pointTag: {
    fontFamily: fonts.mono,
    fontSize: 10.5,
    color: colors.faint,
    width: 34,
    textAlign: "right",
  },
  seg: { flexDirection: "row", gap: 3 },
  segItem: { flex: 1, height: 5, borderRadius: 2 },
  pend: {
    minHeight: 56,
    flexDirection: "row",
    alignItems: "center",
    gap: 11,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.card2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
  pendIdle: { opacity: 0.5 },
  pendIcon: { width: 32, height: 32, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  pendBody: {
    flex: 1,
    // No Yoga o padrão de flex-shrink é 0: sem isto, nome/sub disputam a linha
    // com o contador e estouram num aparelho de 360dp (defeito nº 1 da onda 1).
    flexShrink: 1,
  },
  pendName: { fontFamily: fonts.uiSemi, fontSize: 13.5, color: colors.text },
  pendSub: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted, marginTop: 2 },
  pendContador: { fontFamily: fonts.mono, fontSize: 11, color: colors.text },
  pendFeito: {
    fontFamily: fonts.mono,
    fontSize: 9,
    color: colors.success,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  reward: { padding: spacing.xl, justifyContent: "center" },
  rewardCrumb: {
    fontFamily: fonts.mono,
    fontSize: 9,
    letterSpacing: 1.6,
    color: colors.textMuted,
    textTransform: "uppercase",
    textAlign: "center",
  },
  rewardHero: {
    fontFamily: fonts.displayBold,
    fontSize: 56,
    letterSpacing: -0.5,
    color: colors.text,
    textAlign: "center",
    marginTop: 10,
  },
  rewardHeroLabel: {
    fontFamily: fonts.mono,
    fontSize: 9.5,
    letterSpacing: 2,
    color: colors.textMuted,
    textAlign: "center",
    marginTop: 8,
  },
  rewardCard: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.lg,
    paddingVertical: 15,
    paddingHorizontal: 16,
    marginTop: 20,
  },
  rewardRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  rewardLabel: {
    fontFamily: fonts.mono,
    fontSize: 9.5,
    letterSpacing: 1.4,
    color: colors.textMuted,
  },
  rewardSaldo: {
    fontFamily: fonts.mono,
    fontSize: 16,
    color: colors.text,
    letterSpacing: 0.3,
  },
  rewardSaldoSmall: { fontSize: 11, color: colors.textMuted },
  diams: { flexDirection: "row", gap: 5 },
  diam: {
    width: 8,
    height: 8,
    borderWidth: 1,
    borderColor: LINE_STRONG,
    borderRadius: 2,
    transform: [{ rotate: "45deg" }],
  },
  diamOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  rewardCycleFoot: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 7,
  },
  rewardCycleLeft: { fontFamily: fonts.mono, fontSize: 9, color: colors.faint },
  rewardCycleRight: { fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted },
  rewardGhost: {
    minHeight: 42,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    marginTop: spacing.md,
  },
  rewardGhostText: {
    fontFamily: fonts.mono,
    fontSize: 10.5,
    letterSpacing: 0.4,
    color: colors.textMuted,
  },
});
