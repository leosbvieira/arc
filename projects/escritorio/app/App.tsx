import { Feather } from "@expo/vector-icons";
import { useFonts, Fraunces_500Medium } from "@expo-google-fonts/fraunces";
import {
  IBMPlexMono_500Medium,
} from "@expo-google-fonts/ibm-plex-mono";
import {
  SpaceGrotesk_400Regular,
  SpaceGrotesk_500Medium,
  SpaceGrotesk_600SemiBold,
  SpaceGrotesk_700Bold,
} from "@expo-google-fonts/space-grotesk";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import {
  Alert,
  AppState,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  StatusBar as RNStatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getBffUrl, getToken, login, registerDevice, setBffUrl } from "./src/api";
import { flush } from "./src/captureQueue";
import { registerForPushToken } from "./src/notifications";
import Capture from "./src/screens/Capture";
import Chat from "./src/screens/Chat";
import Fechar from "./src/screens/Fechar";
import Home from "./src/screens/Home";
import Revisao from "./src/screens/Revisao";
import Rotinas from "./src/screens/Rotinas";
import Tasks from "./src/screens/Tasks";
import { colors, fonts, spacing } from "./src/theme";
import { AppButton, Card, Field } from "./src/ui";

type Tab = "home" | "capturar" | "tarefas" | "chat" | "revisao" | "fechar" | "rotinas";

// A tabbar fica só com 4 — revisão/fechar/rotinas entram pela Home e voltam pelo chevron.
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "home", label: "Home", icon: "home" },
  { key: "capturar", label: "Capturar", icon: "feather" },
  { key: "tarefas", label: "Tarefas", icon: "check-square" },
  { key: "chat", label: "Chat", icon: "message-circle" },
];

const SUBSCREENS: Tab[] = ["revisao", "fechar", "rotinas"];

const TITLES: Partial<Record<Tab, string>> = {
  revisao: "Revisão",
  fechar: "Fechar o dia",
  rotinas: "Rotinas",
};

export default function App() {
  const [fontsLoaded] = useFonts({
    Fraunces_500Medium,
    SpaceGrotesk_400Regular,
    SpaceGrotesk_500Medium,
    SpaceGrotesk_600SemiBold,
    SpaceGrotesk_700Bold,
    IBMPlexMono_500Medium,
  });
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("home");

  useEffect(() => {
    getToken().then((t) => {
      setAuthed(!!t);
      setReady(true);
    });
  }, []);

  useEffect(() => {
    getBffUrl().then(setServer);
  }, []);

  useEffect(() => {
    if (!authed) return;

    const sync = () => {
      flush().catch((e) => console.log("capture queue:", e));
    };

    sync();
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") sync();
    });

    return () => sub.remove();
  }, [authed]);

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
      if (server.trim()) {
        await setBffUrl(server);
      }
      await login(password);
      await afterAuth();
    } catch (e: any) {
      Alert.alert("Login", e?.message ?? "falhou");
    } finally {
      setBusy(false);
    }
  }

  if (!ready || !fontsLoaded) {
    return (
      <SafeAreaView style={[styles.screen, styles.center]}>
        <StatusBar style="light" />
        <Text style={styles.brand}>escritório</Text>
      </SafeAreaView>
    );
  }

  if (!authed) {
    return (
      <SafeAreaView style={styles.screen}>
        <StatusBar style="light" />
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={[styles.center, { flex: 1, paddingHorizontal: spacing.xl }]}
        >
          <Text style={styles.brand}>escritório</Text>
          <Text style={styles.tagline}>seu comando pessoal</Text>
          <Card style={{ width: "100%", marginTop: spacing.xl, gap: spacing.md }}>
            <Text style={styles.label}>SENHA</Text>
            <Field
              secureTextEntry
              autoCapitalize="none"
              placeholder="senha do BFF"
              value={password}
              onChangeText={setPassword}
            />
            <Text style={styles.label}>SERVIDOR</Text>
            <Field
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              placeholder="http://192.168.x.x:8000"
              value={server}
              onChangeText={setServer}
            />
            <AppButton title="Entrar" onPress={onLogin} loading={busy} />
          </Card>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  const isFull = tab === "home" || tab === "chat";
  const isSub = SUBSCREENS.includes(tab);
  const title = TITLES[tab] ?? TABS.find((t) => t.key === tab)?.label ?? "";

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="light" />
      {tab !== "home" && (
        <View style={styles.header}>
          {isSub ? (
            <Pressable
              onPress={() => setTab("home")}
              hitSlop={8}
              style={{ flexDirection: "row", alignItems: "center", gap: 4 }}
            >
              <Feather name="chevron-left" size={20} color={colors.text} />
              <Text style={styles.brand}>escritório</Text>
            </Pressable>
          ) : (
            <Text style={styles.brand}>escritório</Text>
          )}
          <Text style={styles.section}>{title}</Text>
        </View>
      )}

      <View style={[styles.content, isFull && { paddingHorizontal: 0 }]}>
        {tab === "home" ? (
          <Home onOpenTab={(t) => setTab(t as Tab)} />
        ) : tab === "capturar" ? (
          <Capture />
        ) : tab === "tarefas" ? (
          <Tasks />
        ) : tab === "chat" ? (
          <Chat />
        ) : tab === "fechar" ? (
          <Fechar />
        ) : tab === "rotinas" ? (
          <Rotinas />
        ) : (
          <Revisao />
        )}
      </View>

      <View style={styles.tabbar}>
        {TABS.map((t) => {
          const active = t.key === tab;
          return (
            <Pressable key={t.key} onPress={() => setTab(t.key)} style={styles.tabItem}>
              <Feather
                name={t.icon as any}
                size={21}
                color={active ? colors.primary : colors.textMuted}
              />
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
  brand: { fontFamily: fonts.uiBold, fontSize: 24, color: colors.text, letterSpacing: -0.5 },
  tagline: { fontFamily: fonts.serif, color: colors.textMuted, marginTop: 6, fontSize: 15 },
  label: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted, letterSpacing: 1 },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
  },
  section: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 15 },
  content: { flex: 1, paddingHorizontal: spacing.lg },
  tabbar: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  tabItem: { flex: 1, alignItems: "center", gap: 4, paddingVertical: 4 },
  tabLabel: { fontFamily: fonts.ui, fontSize: 10.5, color: colors.textMuted },
  tabLabelActive: { color: colors.primary, fontFamily: fonts.uiSemi },
});
