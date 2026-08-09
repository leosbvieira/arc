import { Feather } from "@expo/vector-icons";
import { useEffect, useState } from "react";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getTaskDetail, TaskDetail, adiarTask } from "./api";
import { DueChoice, dueFromChoice } from "./taskDue";
import { areaColor, colors, fonts, radius, spacing } from "./theme";
import { AppButton } from "./ui";

export function TaskDetailModal({
  taskId,
  onClose,
  onComplete,
  onAdiada,
}: {
  taskId: string | null;
  onClose: () => void;
  onComplete?: (id: string) => Promise<boolean | void>;
  /** Chamado após adiar, para a tela recarregar a lista. */
  onAdiada?: () => void;
}) {
  const insets = useSafeAreaInsets();
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [adiando, setAdiando] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;
    let alive = true;
    setDetail(null);
    setConfirming(false);
    setLoading(true);
    getTaskDetail(taskId)
      .then((d) => alive && setDetail(d))
      .catch((e: any) => {
        if (alive) {
          Alert.alert("Detalhe", e?.message ?? "falhou");
          onClose();
        }
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  return (
    <Modal visible={!!taskId} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.scrim} onPress={onClose} />
      <View style={[styles.sheet, { paddingBottom: Math.max(spacing.xl, insets.bottom + spacing.sm) }]}>
        <View style={styles.handle} />
        {loading || !detail ? (
          <ActivityIndicator style={{ marginVertical: 36 }} color={colors.primary} />
        ) : (
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={{ paddingBottom: spacing.lg }}
          >
            <View style={styles.areaRow}>
              <View style={[styles.dot, { backgroundColor: areaColor(detail.area) }]} />
              <Text style={[styles.area, { color: areaColor(detail.area) }]}>
                {detail.area?.toLowerCase()}
              </Text>
              {detail.status ? <Text style={styles.status}>{detail.status}</Text> : null}
            </View>

            <Text style={styles.name}>{detail.name}</Text>

            <View style={styles.meta}>
              {detail.due ? (
                <View style={styles.metaItem}>
                  <Feather name="calendar" size={14} color={colors.textMuted} />
                  <Text style={styles.metaText}>{detail.due}</Text>
                </View>
              ) : null}
              {detail.assignee ? (
                <View style={styles.metaItem}>
                  <Feather name="user" size={14} color={colors.textMuted} />
                  <Text style={styles.metaText}>{detail.assignee}</Text>
                </View>
              ) : null}
              {detail.priority ? (
                <View style={styles.metaItem}>
                  <Feather name="flag" size={14} color={colors.textMuted} />
                  <Text style={styles.metaText}>{detail.priority}</Text>
                </View>
              ) : null}
            </View>

            <Text style={styles.label}>descrição</Text>
            <Text style={styles.desc}>{detail.description ? detail.description : "sem descrição"}</Text>

            <View style={{ height: spacing.lg }} />
            {onComplete ? (
              <>
                {confirming ? (
                  <View style={styles.confirmBox}>
                    <Text style={styles.confirmText}>Confirmar conclusão no ClickUp?</Text>
                    <AppButton
                      title="Confirmar conclusão"
                      loading={completing}
                      onPress={async () => {
                        setCompleting(true);
                        try {
                          if ((await onComplete(detail.id)) !== false) onClose();
                        } finally {
                          setCompleting(false);
                        }
                      }}
                    />
                    <AppButton title="Cancelar" variant="ghost" onPress={() => setConfirming(false)} disabled={completing} />
                  </View>
                ) : (
                  <AppButton title="Concluir tarefa" onPress={() => setConfirming(true)} />
                )}
                <View style={{ height: spacing.sm }} />
              </>
            ) : null}

            {/* Lei 4: replanejar, não envergonhar. Sem isto, a única forma de calar
                uma cobrança era concluir mentindo — e aguentar 🚨 todo dia é o que
                treina a ignorar o digest. */}
            <Text style={styles.label}>adiar para</Text>
            <View style={styles.adiarRow}>
              {([
                { key: "hoje", label: "hoje" },
                { key: "amanha", label: "amanhã" },
                { key: "semana", label: "+7 dias" },
              ] as { key: DueChoice; label: string }[]).map((option) => (
                <Pressable
                  key={option.label}
                  disabled={adiando !== null}
                  onPress={async () => {
                    const due = dueFromChoice(option.key);
                    if (!due) return;
                    setAdiando(option.label);
                    try {
                      await adiarTask(detail.id, due);
                      onAdiada?.();
                      onClose();
                    } catch (error) {
                      Alert.alert(
                        "Adiar",
                        error instanceof Error ? error.message : "Não consegui adiar.",
                      );
                    } finally {
                      setAdiando(null);
                    }
                  }}
                  style={[styles.adiarPill, adiando === option.label && styles.adiarPillBusy]}
                >
                  <Text style={styles.adiarPillText}>{option.label}</Text>
                </Pressable>
              ))}
            </View>
            <View style={{ height: spacing.sm }} />
            {detail.url ? (
              <>
                <AppButton
                  title="Abrir no ClickUp"
                  variant="ghost"
                  onPress={() => Linking.openURL(detail.url!)}
                />
                <View style={{ height: spacing.sm }} />
              </>
            ) : null}
            <AppButton title="Fechar" variant="ghost" onPress={onClose} />
          </ScrollView>
        )}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: "rgba(4,4,6,0.6)" },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
    maxHeight: "82%",
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 4,
    backgroundColor: colors.border,
    marginBottom: spacing.md,
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  areaRow: { flexDirection: "row", alignItems: "center", gap: 7 },
  area: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1, textTransform: "uppercase" },
  status: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.textMuted,
    marginLeft: "auto",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  name: { fontFamily: fonts.uiSemi, fontSize: 22, color: colors.text, marginTop: 8, lineHeight: 28 },
  meta: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginTop: spacing.md },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  metaText: { fontFamily: fonts.ui, fontSize: 13, color: colors.text },
  adiarRow: { flexDirection: "row", gap: spacing.sm },
  adiarPill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  adiarPillBusy: { opacity: 0.5 },
  adiarPillText: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.text },
  label: {
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 1.4,
    textTransform: "uppercase",
    color: colors.textMuted,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  desc: { fontFamily: fonts.ui, fontSize: 14.5, color: colors.text, lineHeight: 21 },
  confirmBox: { gap: spacing.sm, padding: spacing.md, borderWidth: 1, borderColor: "rgba(111,181,140,0.3)", borderRadius: radius.md, backgroundColor: "rgba(111,181,140,0.06)" },
  confirmText: { fontFamily: fonts.uiSemi, fontSize: 12.5, color: colors.text, textAlign: "center" },
});
