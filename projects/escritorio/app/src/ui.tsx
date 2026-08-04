import { Feather } from "@expo/vector-icons";
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
}: {
  eyebrow?: string;
  title: string;
  action?: string;
  onAction?: () => void;
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
      ) : null}
    </View>
  );
}

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
    <View style={[styles.badge, { borderColor: `${color}55` }]}>
      <View style={[styles.badgeDot, { backgroundColor: color }]} />
      <Text style={styles.badgeLabel}>{label}</Text>
      {value !== undefined ? <Text style={[styles.badgeValue, { color }]}>{value}</Text> : null}
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
    fontFamily: fonts.serif,
    fontSize: 21,
    color: colors.text,
    letterSpacing: -0.3,
  },
  sectionAction: { fontFamily: fonts.uiSemi, color: colors.primary, fontSize: 12 },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    minHeight: 32,
    borderWidth: 1,
    backgroundColor: "rgba(255,255,255,0.025)",
    borderRadius: radius.pill,
    paddingHorizontal: 11,
  },
  badgeDot: { width: 5, height: 5, borderRadius: 3 },
  badgeLabel: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  badgeValue: { fontFamily: fonts.mono, fontSize: 11 },
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
});
