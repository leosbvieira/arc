import Feather from "@expo/vector-icons/Feather";
// Caminho PROFUNDO por peso, nunca o barril da família. O barril de
// `@expo-google-fonts/*` faz require() de TODOS os pesos, e importar um só
// torna o conjunto alcançável: o Metro empacotava 26 arquivos .ttf para usar 7
// — 2,3 MB de fonte morta, 1,8 MB deles só de IBM Plex Mono.
//
// `useFonts` vem do `expo-font` direto. Importá-lo de qualquer pacote de fonte
// reabriria o barril daquela família e desfaria a economia sem avisar.
//
// Caminho errado aqui NÃO quebra o build: a fonte só não carrega, o Android cai
// no padrão do sistema, e o app fica com cara de Roboto sem ninguém notar. Se
// mexer nestas linhas, confira no aparelho — `tsc` não pega isso.
import { useFonts } from "expo-font";
import { BricolageGrotesque_400Regular } from "@expo-google-fonts/bricolage-grotesque/400Regular";
import { BricolageGrotesque_500Medium } from "@expo-google-fonts/bricolage-grotesque/500Medium";
import { BricolageGrotesque_600SemiBold } from "@expo-google-fonts/bricolage-grotesque/600SemiBold";
import { BricolageGrotesque_700Bold } from "@expo-google-fonts/bricolage-grotesque/700Bold";
import { IBMPlexMono_500Medium } from "@expo-google-fonts/ibm-plex-mono/500Medium";
import { Syne_600SemiBold } from "@expo-google-fonts/syne/600SemiBold";
import { Syne_700Bold } from "@expo-google-fonts/syne/700Bold";
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
import Agenda from "./src/screens/Agenda";
import { getBffUrl, getToken, login, registerDevice, setBffUrl, unregisterDevice } from "./src/api";
import { sessaoValida } from "./src/sessao";
import { flush } from "./src/captureQueue";
import {
  esquecerPushToken,
  getRegisteredPushToken,
  lembrarPushToken,
  obterPushToken,
} from "./src/notifications";
import { comPrazoAbortavel } from "./src/prazo";
import { sincronizarPush } from "./src/pushSync";
import Capture from "./src/screens/Capture";
import Chat from "./src/screens/Chat";
import Edificacao from "./src/screens/Edificacao";
import Fechar from "./src/screens/Fechar";
import Habitos from "./src/screens/Habitos";
import Home from "./src/screens/Home";
import Melhorias from "./src/screens/Melhorias";
import Mesa from "./src/screens/Mesa";
import { ParametrosProvider } from "./src/parametros";
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
  | "mesa"
  | "capturar"
  | "tarefas"
  | "chat"
  | "revisao"
  | "abertura"
  | "agenda"
  | "shutdown"
  | "fechar"
  | "rotinas"
  | "edificacao"
  | "melhorias"
  | "triagem"
  | "habitos"
  | "settings";

// A Mesa é a 5ª aba e substitui a gaveta "Ferramentas" que saiu da Home —
// por isso fica em segundo. Revisão/abertura/shutdown/fechar/rotinas seguem
// subtelas e voltam pelo chevron.
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "home", label: "Hoje", icon: "circle" },
  { key: "mesa", label: "Mesa", icon: "grid" },
  { key: "capturar", label: "Capturar", icon: "feather" },
  { key: "tarefas", label: "Tarefas", icon: "check-square" },
  { key: "chat", label: "Mentor", icon: "message-circle" },
];

const SUBSCREENS: Tab[] = [
  "revisao",
  "abertura",
  "agenda",
  "shutdown",
  "fechar",
  "rotinas",
  "edificacao",
  "melhorias",
  "triagem",
  "habitos",
  "settings",
];

const TITLES: Partial<Record<Tab, string>> = {
  revisao: "Revisão",
  abertura: "Abertura",
  agenda: "Agenda",
  shutdown: "Shutdown",
  fechar: "Fechar o dia",
  rotinas: "Ritmos",  // as duas portas (Home e Mesa) já diziam "Ritmos"
  edificacao: "Edificação",
  melhorias: "Melhorias",
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

const PRAZO_PUSH_MS = 8000;

async function syncPushDevice() {
  // A regra (rotação, revogação, quando esquecer) mora em `pushSync.ts`, puro e
  // testado. Aqui só a fiação. Cada chamada ao BFF tem prazo: o boot não pode
  // ficar preso atrás de um servidor que aceita a conexão e não responde.
  const resultado = await sincronizarPush({
    registrado: getRegisteredPushToken,
    atual: obterPushToken,
    registerDevice: (t) =>
      comPrazoAbortavel((signal) => registerDevice(t, signal), PRAZO_PUSH_MS, "registrar push"),
    unregisterDevice: (t) =>
      comPrazoAbortavel((signal) => unregisterDevice(t, signal), PRAZO_PUSH_MS, "remover push"),
    lembrar: lembrarPushToken,
    esquecer: esquecerPushToken,
  });
  if (resultado.tipo !== "registrado") console.log("push:", resultado);
}

export default function App() {
  const [fontsLoaded, fontsError] = useFonts({
    BricolageGrotesque_400Regular,
    BricolageGrotesque_500Medium,
    BricolageGrotesque_600SemiBold,
    BricolageGrotesque_700Bold,
    Syne_600SemiBold,
    Syne_700Bold,
    IBMPlexMono_500Medium,
  });
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("home");
  // De onde a subtela veio — gravado antes de trocar de aba. Entrou pela Mesa,
  // volta para a Mesa; entrou por notificação das 21h, volta para Hoje.
  const [origem, setOrigem] = useState<Tab>("home");
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
    // Guarda de onde veio ANTES de trocar de aba quando o destino for subtela —
    // o chevron e o botão físico voltam para lá, não para um literal "home".
    if (SUBSCREENS.includes(destination as Tab)) setOrigem(tab);
    setTab(destination as Tab);
  }

  useEffect(() => {
    // Três defeitos moravam nestas cinco linhas.
    //
    // (1) `!!t` decidia autenticação pela EXISTÊNCIA do token, nunca pela validade.
    // Com TTL de 30 dias, o dia 31 abria a tabbar inteira em "erro 401" sem nenhum
    // caminho de volta ao login. Agora a validade é lida do próprio token, offline.
    // (2) Sem `.catch`, uma rejeição do expo-secure-store (restore de aparelho,
    // keystore invalidada) deixava `ready=false` PARA SEMPRE: splash permanente com
    // uma palavra, sem erro e sem retry, e a única saída era limpar os dados do app
    // — que leva junto a fila offline e o rascunho de leitura.
    // (3) `setReady` fora do `.finally` tinha o mesmo efeito em qualquer outra falha.
    getToken()
      .then((t) => {
        const autenticado = sessaoValida(t, Date.now());
        setAuthed(autenticado);
        if (autenticado) startPushSync();
        // NÃO apaga o token vencido. `setAuthed(false)` já leva à tela de login e o
        // `login()` grava por cima, então apagar não comprava nada — e comprava um
        // risco: a decisão sai do relógio LOCAL, então um aparelho com a hora
        // adiantada destruía uma credencial boa, de forma irreversível.
      })
      .catch((e) => {
        console.log("sessão:", e);
        setAuthed(false);
      })
      .finally(() => setReady(true));
  }, []);

  useEffect(() => {
    getBffUrl().then(setServer);
  }, []);

  useEffect(() => {
    if (!authed) return;

    const sync = () => {
      // A validade também se reconfere aqui. A checagem do boot só roda uma vez, e o
      // app fica aberto por dias: o token vencia com ele em pé e o defeito voltava
      // inteiro — tabbar em "erro 401" e nenhum caminho de volta ao login.
      getToken()
        .then((t) => {
          if (!sessaoValida(t, Date.now())) setAuthed(false);
        })
        .catch(() => {});
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
      // Subtela volta para a origem; aba volta para Hoje. Sem isso, origem
      // sozinha criaria armadilha (Mesa → Mesa e o Android nunca sai do app).
      setTab(SUBSCREENS.includes(tab) ? origem : "home");
      return true;
    });
    return () => subscription.remove();
  }, [authed, tab, origem]);

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

  // `fontsError` entra na condição: o gate era `!ready || !fontsLoaded` e só `ready`
  // ganhou tratamento de falha. Com a fonte falhando (rede no primeiro boot), o app
  // ficava no mesmo splash permanente pela outra metade da condição. Melhor abrir com
  // a fonte do sistema do que não abrir.
  if (!ready || (!fontsLoaded && !fontsError)) {
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

  // A Mesa tem cabeçalho próprio (eyebrow + título em display): com o header
  // do App seriam dois títulos empilhados. Por isso isFull inclui mesa e o
  // header some nela, como já acontece na Home.
  const isFull = tab === "home" || tab === "chat" || tab === "mesa";
  const isSub = SUBSCREENS.includes(tab);
  const title = TITLES[tab] ?? TABS.find((t) => t.key === tab)?.label ?? "";

  return (
    <ParametrosProvider>
    <SafeAreaProvider>
      <SafeAreaView style={styles.screen}>
      <StatusBar style="light" />
      {tab !== "home" && tab !== "mesa" && (
        <View style={styles.header}>
          {isSub ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Voltar"
              onPress={() => setTab(origem)}
              hitSlop={8}
              style={styles.back}
            >
              <Feather name="arrow-left" size={17} color={colors.text} />
            </Pressable>
          ) : (
            <Text style={styles.brandSmall}>AETERNUM</Text>
          )}
          <Text style={styles.section} numberOfLines={1}>{title}</Text>
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
        ) : tab === "mesa" ? (
          <Mesa onOpenTab={openDestination} />
        ) : tab === "tarefas" ? (
          <Tasks initialTaskId={initialTaskId} onInitialTaskConsumed={() => setInitialTaskId(null)} />
        ) : tab === "agenda" ? (
          <Agenda />
        ) : tab === "abertura" ? (
          <Abertura />
        ) : tab === "shutdown" ? (
          <Shutdown onOpenTriagem={() => setTab("triagem")} />
        ) : tab === "fechar" ? (
          <Fechar />
        ) : tab === "rotinas" ? (
          <Rotinas />
        ) : tab === "edificacao" ? (
          <Edificacao />
        ) : tab === "melhorias" ? (
          <Melhorias />
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
            onOpenMelhorias={() => setTab("melhorias")}
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
    </ParametrosProvider>
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
  tagline: { fontFamily: fonts.ui, color: colors.textMuted, marginTop: 6, fontSize: 15 },
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
  // Syne é expandida e o Yoga tem flexShrink padrão 0: sem encolher, um título
  // longo ("Hábitos a reduzir") estoura a linha entre os dois blocos de 72px.
  section: { fontFamily: fonts.display, color: colors.text, fontSize: 20, letterSpacing: -0.2, flexShrink: 1 },
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
