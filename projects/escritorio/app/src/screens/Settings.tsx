import Feather from "@expo/vector-icons/Feather";
import { useEffect, useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";

import { clearToken, getBffUrl, setBffUrl, unregisterDevice } from "../api";
import { performLogout } from "../logout";
import { disableLocalPush, getRegisteredPushToken } from "../notifications";
import { colors, fonts, spacing } from "../theme";
import { AppButton, Card, Field } from "../ui";

export default function Settings({
  onLogout,
  onServerSaved,
  beforeLogout,
}: {
  onLogout: () => void;
  onServerSaved: (url: string) => void;
  beforeLogout: () => Promise<void>;
}) {
  const [server, setServer] = useState("");
  const [status, setStatus] = useState<"idle" | "checking" | "online" | "offline">("idle");
  const [saving, setSaving] = useState(false);

  useEffect(() => { getBffUrl().then(setServer); }, []);

  async function check() {
    setStatus("checking");
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      const response = await fetch(`${server.trim().replace(/\/+$/, "")}/health`, { signal: controller.signal });
      clearTimeout(timer);
      setStatus(response.ok ? "online" : "offline");
    } catch {
      setStatus("offline");
    }
  }

  async function save() {
    if (!server.trim()) return;
    setSaving(true);
    try {
      await setBffUrl(server);
      const salva = await getBffUrl();
      setServer(salva);
      onServerSaved(salva);
    } catch (e: any) {
      // Endereço recusado (esquema, credencial, http num build https-only): o
      // valor antigo continua valendo e o motivo aparece — antes salvava qualquer
      // coisa e o erro só aparecia como "offline" no check.
      Alert.alert("Servidor", e?.message ?? "endereço inválido");
      setSaving(false);
      return;
    }
    setSaving(false);
    await check();
  }

  function logout() {
    Alert.alert("Sair do Escritório?", "Você precisará informar a senha do BFF novamente.", [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Sair",
        style: "destructive",
        onPress: async () => {
          try {
            await beforeLogout();
          } catch {
            /* best-effort: nada aqui pode impedir a saída */
          }
          const { serverOk } = await performLogout({
            // Só o token REGISTRADO. Antes caía em `registerForPushToken()`, que pede
            // permissão ao sistema — um diálogo de permissão no meio do "Sair".
            pushToken: getRegisteredPushToken,
            unregisterDevice,
            disableLocalPush,
            clearToken,
          });
          onLogout();
          if (!serverOk) {
            Alert.alert(
              "Você saiu deste aparelho",
              "Não consegui avisar o servidor para parar as notificações — pode ser sessão expirada ou falta de conexão. Se elas continuarem, entre de novo e saia com o servidor acessível.",
            );
          }
        },
      },
    ]);
  }

  const statusColor = status === "online" ? colors.success : status === "offline" ? colors.danger : colors.textMuted;
  const statusLabel = status === "checking" ? "testando…" : status === "online" ? "servidor online" : status === "offline" ? "servidor indisponível" : "ainda não testado";

  return (
    <View style={styles.content}>
      <Card style={styles.card}>
        <View style={styles.heading}>
          <View style={styles.icon}><Feather name="server" size={18} color={colors.primary} /></View>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Conexão do Escritório</Text>
            <View style={styles.statusRow}><View style={[styles.dot, { backgroundColor: statusColor }]} /><Text style={[styles.status, { color: statusColor }]}>{statusLabel}</Text></View>
          </View>
        </View>
        <Text style={styles.label}>ENDEREÇO DO BFF</Text>
        <Field value={server} onChangeText={(value) => { setServer(value); setStatus("idle"); }} autoCapitalize="none" autoCorrect={false} keyboardType="url" placeholder="http://192.168.0.2:8000" />
        <Text style={styles.hint}>No celular, use o IP do computador na mesma rede. O valor fica protegido no aparelho.</Text>
        <AppButton title="Salvar e testar" onPress={save} loading={saving || status === "checking"} disabled={!server.trim()} />
      </Card>

      <Card style={styles.card}>
        <Text style={styles.label}>SESSÃO</Text>
        <Text style={styles.sessionTitle}>Acesso autenticado</Text>
        <Text style={styles.hint}>Sair encerra a sessão e remove este aparelho das notificações. Capturas locais e dados do servidor não são apagados.</Text>
        <AppButton title="Sair deste aparelho" variant="ghost" onPress={logout} />
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing.md, paddingTop: spacing.sm },
  card: { gap: spacing.md },
  heading: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  icon: { width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: colors.primarySoft },
  title: { fontFamily: fonts.uiSemi, fontSize: 19, color: colors.text },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 4 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  status: { fontFamily: fonts.mono, fontSize: 9.5 },
  label: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1.2, color: colors.textMuted },
  hint: { fontFamily: fonts.ui, fontSize: 11.5, lineHeight: 17, color: colors.textMuted },
  sessionTitle: { fontFamily: fonts.uiSemi, fontSize: 14, color: colors.text },
});
