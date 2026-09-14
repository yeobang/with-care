/**
 * 인앱 토스트 — window.alert / Alert.alert 대체.
 * 화면은 notify()만 부르고, 실제 표시는 ToastHost가 맡는다 (화면들이 UI를 몰라도 되게).
 */
export type ToastTone = "info" | "success" | "error";
export interface ToastItem {
  id: number;
  title: string;
  message?: string;
  tone: ToastTone;
}

type Listener = (item: ToastItem) => void;
let listener: Listener | null = null;
let seq = 0;

export function setToastListener(l: Listener | null) {
  listener = l;
}

export function notify(title: string, message?: string, tone: ToastTone = "info") {
  const item: ToastItem = { id: ++seq, title, message, tone };
  if (listener) listener(item);
  else console.warn(`[notify] ${title}${message ? " — " + message : ""}`);
}

/** 실패 알림용 단축 — 가드레일 위반은 코드까지 보여준다. */
export function notifyError(e: any, fallback = "잠시 후 다시 시도해주세요") {
  const msg = e?.message ?? fallback;
  notify(e?.invariant ? "안전 규칙에 막혔어요" : "오류", msg, "error");
}
