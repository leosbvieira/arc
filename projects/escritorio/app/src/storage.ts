import * as NativeSecureStore from "expo-secure-store";
import { Platform } from "react-native";

function webStorage(): Storage | null {
  if (Platform.OS !== "web" || typeof globalThis.localStorage === "undefined") {
    return null;
  }
  return globalThis.localStorage;
}

export async function getItemAsync(key: string): Promise<string | null> {
  const storage = webStorage();
  return storage ? storage.getItem(key) : NativeSecureStore.getItemAsync(key);
}

export async function setItemAsync(key: string, value: string): Promise<void> {
  const storage = webStorage();
  if (storage) {
    storage.setItem(key, value);
    return;
  }
  await NativeSecureStore.setItemAsync(key, value);
}

export async function deleteItemAsync(key: string): Promise<void> {
  const storage = webStorage();
  if (storage) {
    storage.removeItem(key);
    return;
  }
  await NativeSecureStore.deleteItemAsync(key);
}
