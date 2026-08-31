import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { api } from "./api";

/** Expo 푸시 토큰 등록 — best-effort. 웹·시뮬레이터·EAS 미설정이면 조용히 건너뛴다. */
export async function registerPush(): Promise<void> {
  try {
    if (Platform.OS === "web") return;
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== "granted") return;
    const projectId = (Constants.expoConfig as any)?.extra?.eas?.projectId;
    const token = (
      await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined)
    ).data;
    if (token) await api.post("/push/tokens", { token });
  } catch {
    // 알림은 부가 기능 — 등록 실패가 앱을 막지 않는다
  }
}
