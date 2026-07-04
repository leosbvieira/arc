import { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";

import { capture } from "../api";
import { colors, spacing } from "../theme";
import { AppButton, Card, Field } from "../ui";

export default function Capture() {
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSend() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const r = await capture(text.trim());
      setReply(r);
      setText("");
    } catch (e: any) {
      Alert.alert("Erro", e?.message ?? "falhou");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ flex: 1, gap: spacing.md, paddingTop: spacing.sm }}>
      <Text style={styles.hint}>Fala ou digita — vira tarefa ou nota.</Text>
      <Field
        style={styles.input}
        value={text}
        onChangeText={setText}
        placeholder="ex.: cobrar Ana o relatório sexta"
        multiline
      />
      <AppButton title="Enviar" onPress={onSend} loading={busy} />
      {reply ? (
        <Card style={styles.reply}>
          <Text style={{ fontSize: 18 }}>✅</Text>
          <Text style={styles.replyText}>{reply}</Text>
        </Card>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  hint: { color: colors.textMuted, fontSize: 13 },
  input: { minHeight: 120, textAlignVertical: "top" },
  reply: { marginTop: spacing.sm, flexDirection: "row", gap: spacing.sm },
  replyText: { flex: 1, color: colors.text, fontSize: 15, lineHeight: 21 },
});
