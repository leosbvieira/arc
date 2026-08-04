import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
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
 * Pede permissão e devolve o Expo push token (ou null se não der).
 * Retorna null em: emulador, permissão negada, ou sem projectId (Expo Go /
 * sem `eas init`). O push remoto só funciona num dev build (EAS), não no Expo Go.
 */
export async function registerForPushToken(): Promise<string | null> {
  if (!Device.isDevice) return null;

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
  if (status !== "granted") return null;

  const projectId =
    Constants?.expoConfig?.extra?.eas?.projectId ??
    (Constants as any)?.easConfig?.projectId;
  if (!projectId) {
    console.log("Sem projectId — rode `eas init` e faça um dev build pra ter push.");
    return null;
  }

  const token = await Notifications.getExpoPushTokenAsync({ projectId });
  await SecureStore.setItemAsync(REGISTERED_PUSH_TOKEN, token.data);
  return token.data;
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
