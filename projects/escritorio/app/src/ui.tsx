import { Feather } from "@expo/vector-icons";
import { ReactNode, useEffect, useRef } from "react";
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
      <Pressable onPress={onRetry} style={styles.errBtn}>
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
