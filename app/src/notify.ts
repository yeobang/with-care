import { Alert, Platform } from "react-native";

/** 크로스플랫폼 알림 — react-native-web의 Alert.alert는 no-op이라 웹에선 window.alert 사용. */
export function notify(title: string, message?: string) {
  if (Platform.OS === "web") {
    // eslint-disable-next-line no-alert
    window.alert(message ? `${title}\n\n${message}` : title);
  } else {
    Alert.alert(title, message);
  }
}
