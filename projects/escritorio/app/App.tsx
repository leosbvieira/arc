import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  StatusBar as RNStatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getToken, login, registerDevice } from "./src/api";
import { registerForPushToken } from "./src/notifications";
import Capture from "./src/screens/Capture";
import Revisao from "./src/screens/Revisao";
import Tasks from "./src/screens/Tasks";
import { colors, spacing } from "./src/theme";
import { AppButton, Card, Field } from "./src/ui";

type Tab = "capturar" | "tarefas" | "revisao";

const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "capturar", label: "Capturar", icon: "✍️" },
  { key: "tarefas", label: "Tarefas", icon: "📋" },
  { key: "revisao", label: "Revisão", icon: "🔔" },
];

export default function App() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("capturar");

  useEffect(() => {
    getToken().then((t) => {
      setAuthed(!!t);
      setReady(true);
    });
  }, []);

  async function afterAuth() {
    setAuthed(true);
    try {
      const et = await registerForPushToken();
      if (et) await registerDevice(et);
    } catch (e) {
      console.log("push:", e);
    }
  }

  async function onLogin() {
    setBusy(true);
    try {
      await login(password);
      await afterAuth();
    } catch (e: any) {
      Alert.alert("Login", e?.message ?? "falhou");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return (
      <SafeAreaView style={[styles.screen, styles.center]}>
        <StatusBar style="dark" />
        <Text style={styles.brand}>escritório</Text>
      </SafeAreaView>
    );
  }

  if (!authed) {
    return (
      <SafeAreaView style={styles.screen}>
        <StatusBar style="dark" />
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={[styles.center, { flex: 1, paddingHorizontal: spacing.xl }]}
        >
          <Text style={styles.brand}>escritório</Text>
          <Text style={styles.tagline}>seu comando pessoal</Text>
          <Card style={{ width: "100%", marginTop: spacing.xl, gap: spacing.md }}>
            <Text style={styles.label}>Senha</Text>
            <Field
              secureTextEntry
              autoCapitalize="none"
              placeholder="senha do BFF"
              value={password}
              onChangeText={setPassword}
            />
            <AppButton title="Entrar" onPress={onLogin} loading={busy} />
          </Card>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  const current = TABS.find((t) => t.key === tab)!;

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <Text style={styles.brand}>escritório</Text>
        <Text style={styles.section}>{current.label}</Text>
      </View>

      <View style={styles.content}>
        {tab === "capturar" ? <Capture /> : tab === "tarefas" ? <Tasks /> : <Revisao />}
      </View>

      <View style={styles.tabbar}>
        {TABS.map((t) => {
          const active = t.key === tab;
          return (
            <Pressable key={t.key} onPress={() => setTab(t.key)} style={styles.tabItem}>
              <Text style={[styles.tabIcon, { opacity: active ? 1 : 0.4 }]}>{t.icon}</Text>
              <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>{t.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bg,
    paddingTop: Platform.OS === "android" ? RNStatusBar.currentHeight ?? 0 : 0,
  },
  center: { alignItems: "center", justifyContent: "center" },
  brand: { fontSize: 26, fontWeight: "800", color: colors.text, letterSpacing: -0.5 },
  tagline: { color: colors.textMuted, marginTop: 4 },
  label: { fontSize: 13, color: colors.textMuted, fontWeight: "600" },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
  },
  section: { color: colors.textMuted, fontSize: 15, fontWeight: "600" },
  content: { flex: 1, paddingHorizontal: spacing.lg },
  tabbar: {
    flexDirection: "row",
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  tabItem: { flex: 1, alignItems: "center", gap: 2, paddingVertical: 4 },
  tabIcon: { fontSize: 20 },
  tabLabel: { fontSize: 11, color: colors.textMuted },
  tabLabelActive: { color: colors.primary, fontWeight: "700" },
});
