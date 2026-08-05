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
import * as Notifications from "expo-notifications";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  AppState,
  BackHandler,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import Abertura from "./src/screens/Abertura";
import { getBffUrl, getToken, login, registerDevice, setBffUrl } from "./src/api";
import { flush } from "./src/captureQueue";
import { registerForPushToken } from "./src/notifications";
import Capture from "./src/screens/Capture";
import Chat from "./src/screens/Chat";
import Edificacao from "./src/screens/Edificacao";
import Fechar from "./src/screens/Fechar";
import Habitos from "./src/screens/Habitos";
import Home from "./src/screens/Home";
import Revisao from "./src/screens/Revisao";
import Rotinas from "./src/screens/Rotinas";
import Shutdown from "./src/screens/Shutdown";
import Settings from "./src/screens/Settings";
import Tasks from "./src/screens/Tasks";
import Triagem from "./src/screens/Triagem";
import { colors, fonts, radius, spacing } from "./src/theme";
import { AppButton, Card, Field } from "./src/ui";

type Tab =
  | "home"
  | "capturar"
  | "tarefas"
  | "chat"
  | "revisao"
  | "abertura"
  | "shutdown"
  | "fechar"
  | "rotinas"
  | "edificacao"
  | "triagem"
  | "habitos"
  | "settings";

// A tabbar fica só com 4 — revisão/abertura/shutdown/fechar/rotinas entram pela
// Home e voltam pelo chevron.
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "home", label: "Hoje", icon: "circle" },
  { key: "capturar", label: "Capturar", icon: "feather" },
  { key: "tarefas", label: "Tarefas", icon: "check-square" },
  { key: "chat", label: "Mentor", icon: "message-circle" },
];

const SUBSCREENS: Tab[] = [
  "revisao",
  "abertura",
  "shutdown",
  "fechar",
  "rotinas",
  "edificacao",
  "triagem",
  "habitos",
  "settings",
];

const TITLES: Partial<Record<Tab, string>> = {
  revisao: "Revisão",
  abertura: "Abertura",
  shutdown: "Shutdown",
  fechar: "Fechar o dia",
  rotinas: "Rotinas",
  edificacao: "Edificação",
  triagem: "Triagem",
  habitos: "Hábitos a reduzir",
  settings: "Ajustes",
};

function tabDaNotificacao(kind: unknown): Tab | null {
  if (typeof kind !== "string") return null;
  if (kind === "nudge_toque" || kind === "nudge_checkin" || kind === "hora_marcada") {
    return "abertura";
  }
  if (kind === "nudge_shutdown") return "shutdown";
  if (kind === "nudge_closing") return "fechar";
  if (kind === "nudge_review" || kind === "digest") return "revisao";
  if (kind === "nudge_jornal") return "capturar";
  if (kind === "captura" || kind === "capture") return "capturar";
  return null;
}

async function syncPushDevice() {
  const expoToken = await registerForPushToken();
  if (expoToken) await registerDevice(expoToken);
}

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
  const [captureMode, setCaptureMode] = useState<"captura" | "leitura">("captura");
  const [captureRequestId, setCaptureRequestId] = useState(0);
  const [initialTaskId, setInitialTaskId] = useState<string | null>(null);
  const pushSyncRef = useRef<Promise<void>>(Promise.resolve());

  function startPushSync() {
    const operation = syncPushDevice();
    pushSyncRef.current = operation;
    operation.catch((error) => console.log("push:", error));
  }

  function openDestination(destination: string) {
    if (destination === "leitura") {
      setCaptureMode("leitura");
      setCaptureRequestId((current) => current + 1);
      setTab("capturar");
      return;
    }
    if (destination.startsWith("tarefa:")) {
      setInitialTaskId(destination.slice("tarefa:".length));
      setTab("tarefas");
      return;
    }
    if (destination === "capturar") {
      setCaptureMode("captura");
      setCaptureRequestId((current) => current + 1);
    }
    setTab(destination as Tab);
  }

  useEffect(() => {
    getToken().then((t) => {
      const autenticado = !!t;
      setAuthed(autenticado);
      setReady(true);
      if (autenticado) startPushSync();
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

  useEffect(() => {
    if (!authed) return;
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      if (tab === "home") return false;
      setTab("home");
      return true;
    });
    return () => subscription.remove();
  }, [authed, tab]);

  useEffect(() => {
    if (!authed) return;

    const abrir = (response: Notifications.NotificationResponse | null) => {
      const kind = response?.notification.request.content.data?.kind;
      const destino = tabDaNotificacao(kind);
      if (destino === "capturar") {
        setCaptureMode("captura");
        setCaptureRequestId((current) => current + 1);
        setTab("capturar");
      } else if (destino) {
        setTab(destino);
      }
    };

    Notifications.getLastNotificationResponseAsync()
      .then((response) => {
        abrir(response);
        if (response) return Notifications.clearLastNotificationResponseAsync();
        return undefined;
      })
      .catch(() => undefined);
    const sub = Notifications.addNotificationResponseReceivedListener(abrir);
    return () => sub.remove();
  }, [authed]);

  async function afterAuth() {
    setAuthed(true);
    startPushSync();
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
      <SafeAreaProvider>
        <SafeAreaView style={[styles.screen, styles.center]}>
          <StatusBar style="light" />
          <Text style={styles.brand}>escritório</Text>
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  if (!authed) {
    return (
      <SafeAreaProvider>
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
      </SafeAreaProvider>
    );
  }

  const isFull = tab === "home" || tab === "chat";
  const isSub = SUBSCREENS.includes(tab);
  const title = TITLES[tab] ?? TABS.find((t) => t.key === tab)?.label ?? "";

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.screen}>
      <StatusBar style="light" />
      {tab !== "home" && (
        <View style={styles.header}>
          {isSub ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Voltar para Hoje"
              onPress={() => setTab("home")}
              hitSlop={8}
              style={styles.back}
            >
              <Feather name="arrow-left" size={17} color={colors.text} />
            </Pressable>
          ) : (
            <Text style={styles.brandSmall}>AETERNUM</Text>
          )}
          <Text style={styles.section}>{title}</Text>
          {isSub ? <Text style={styles.brandSmall}>AETERNUM</Text> : <View style={{ width: 72 }} />}
        </View>
      )}

      <View style={[styles.content, isFull && { paddingHorizontal: 0 }]}>
        <View style={tab === "capturar" ? styles.mountedScreen : styles.hiddenScreen}>
          <Capture
            initialMode={captureMode}
            modeRequestId={captureRequestId}
            active={tab === "capturar"}
          />
        </View>
        {/* O Chat fica montado como o Capture: desmontar a cada troca de aba
            apagava a conversa inteira — e o Mentor já não tinha memória nenhuma. */}
        <View style={tab === "chat" ? styles.mountedScreen : styles.hiddenScreen}>
          <Chat />
        </View>
        {tab === "capturar" || tab === "chat" ? null : tab === "home" ? (
          <Home onOpenTab={openDestination} />
        ) : tab === "tarefas" ? (
          <Tasks initialTaskId={initialTaskId} onInitialTaskConsumed={() => setInitialTaskId(null)} />
        ) : tab === "abertura" ? (
          <Abertura />
        ) : tab === "shutdown" ? (
          <Shutdown />
        ) : tab === "fechar" ? (
          <Fechar />
        ) : tab === "rotinas" ? (
          <Rotinas />
        ) : tab === "edificacao" ? (
          <Edificacao />
        ) : tab === "triagem" ? (
          <Triagem />
        ) : tab === "habitos" ? (
          <Habitos />
        ) : tab === "settings" ? (
          <Settings
            onServerSaved={setServer}
            beforeLogout={() => pushSyncRef.current.catch(() => undefined)}
            onLogout={() => { setAuthed(false); setTab("home"); }}
          />
        ) : (
          <Revisao
            onOpenCapture={() => openDestination("capturar")}
            onOpenEdificacao={() => setTab("edificacao")}
          />
        )}
      </View>

      <View style={styles.tabbar}>
        {TABS.map((t) => {
          const active = t.key === tab;
          return (
            <Pressable
              key={t.key}
              accessibilityRole="tab"
              accessibilityLabel={t.label}
              accessibilityState={{ selected: active }}
              onPress={() => t.key === "capturar" ? setTab("capturar") : openDestination(t.key)}
              style={[styles.tabItem, active && styles.tabItemActive]}
            >
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
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  center: { alignItems: "center", justifyContent: "center" },
  mountedScreen: { flex: 1 },
  hiddenScreen: { display: "none" },
  brand: { fontFamily: fonts.uiBold, fontSize: 24, color: colors.text, letterSpacing: -0.5 },
  tagline: { fontFamily: fonts.serif, color: colors.textMuted, marginTop: 6, fontSize: 15 },
  label: { fontFamily: fonts.mono, fontSize: 11, color: colors.textMuted, letterSpacing: 1 },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  back: { width: 38, height: 38, borderRadius: 13, alignItems: "center", justifyContent: "center", backgroundColor: colors.card2, borderWidth: 1, borderColor: colors.border },
  brandSmall: { width: 72, fontFamily: fonts.mono, fontSize: 8, color: colors.textMuted, letterSpacing: 1.2 },
  section: { fontFamily: fonts.serif, color: colors.text, fontSize: 20, letterSpacing: -0.35 },
  content: { flex: 1, paddingHorizontal: spacing.lg },
  tabbar: {
    flexDirection: "row",
    backgroundColor: "#0C0F13",
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingHorizontal: spacing.sm,
    paddingTop: 7,
    paddingBottom: 10,
    gap: 4,
  },
  tabItem: { flex: 1, minHeight: 52, alignItems: "center", justifyContent: "center", gap: 4, paddingVertical: 4, borderRadius: radius.md },
  tabItemActive: { backgroundColor: colors.primarySoft },
  tabLabel: { fontFamily: fonts.ui, fontSize: 10, color: colors.textMuted },
  tabLabelActive: { color: colors.primary, fontFamily: fonts.uiSemi },
});
