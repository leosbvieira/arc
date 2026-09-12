import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import type { EstadoDoToken } from "./pushSync";
import * as SecureStore from "./storage";

const REGISTERED_PUSH_TOKEN = "registered_expo_push_token_v1";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/**
 * O token de push de agora — ou POR QUE não há um. Não persiste nada: quem grava é
 * `sincronizarPush`, depois que o BFF confirmou o registro (ver `pushSync.ts`).
 * Motivos: emulador; permissão negada (pede uma vez; se o Leo recusar ou tiver
 * desligado nas configurações, cai aqui); sem projectId (Expo Go / sem `eas init`).
 * O push remoto só funciona num dev build (EAS), não no Expo Go.
 */
export async function obterPushToken(): Promise<EstadoDoToken> {
  if (!Device.isDevice) return { token: null, motivo: "emulador" };

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name: "default",
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }

  let status = (await Notifications.getPermissionsAsync()).status;
  if (status !== "granted") {
    status = (await Notifications.requestPermissionsAsync()).status;
  }
  if (status !== "granted") return { token: null, motivo: "permissao_negada" };

  const projectId =
    Constants?.expoConfig?.extra?.eas?.projectId ??
    (Constants as any)?.easConfig?.projectId;
  if (!projectId) {
    console.log("Sem projectId — rode `eas init` e faça um dev build pra ter push.");
    return { token: null, motivo: "sem_projectId" };
  }

  const token = await Notifications.getExpoPushTokenAsync({ projectId });
  return { token: token.data, motivo: "ok" };
}

export async function lembrarPushToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(REGISTERED_PUSH_TOKEN, token);
}

export async function esquecerPushToken(): Promise<void> {
  await SecureStore.deleteItemAsync(REGISTERED_PUSH_TOKEN);
}

export async function getRegisteredPushToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REGISTERED_PUSH_TOKEN);
}

export async function disableLocalPush(): Promise<void> {
  try {
    await Notifications.unregisterForNotificationsAsync();
  } catch {
    // O token já foi removido do BFF; esta etapa só limpa o registro nativo local.
  } finally {
    await SecureStore.deleteItemAsync(REGISTERED_PUSH_TOKEN);
  }
}
