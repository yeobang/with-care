import { Platform, Share } from "react-native";
import { notify } from "./notify";

export const WEB_ORIGIN = "https://with-care-web.fly.dev";

export const inviteUrl = (token: string) => `${WEB_ORIGIN}/invite/${token}`;

/** 단톡방에 그대로 붙여넣을 문구. 링크만 던지면 아무도 안 누른다. */
export function inviteMessage(crewName: string, token: string): string {
  return [
    `[${crewName}] 아이 돌봄, 이제 여기서 맞춰요`,
    "",
    "되는 시간만 누르면 앱이 짝을 맞춰주고,",
    "누가 얼마나 봐줬는지도 대신 세어줘요.",
    "(돈은 앱이 만지지 않아요 — 계산만 해줍니다)",
    "",
    inviteUrl(token),
  ].join("\n");
}

async function copyToClipboard(text: string): Promise<boolean> {
  if (Platform.OS !== "web") return false;
  try {
    await (navigator as any).clipboard.writeText(text);
    return true;
  } catch {
    // 구형 브라우저·비보안 컨텍스트 폴백
    try {
      const el = document.createElement("textarea");
      el.value = text;
      el.style.position = "fixed";
      el.style.opacity = "0";
      document.body.appendChild(el);
      el.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(el);
      return ok;
    } catch {
      return false;
    }
  }
}

/**
 * 초대 문구를 공유한다.
 * 네이티브는 OS 공유 시트(카톡 포함), 웹은 Web Share API → 없으면 클립보드 복사.
 * 어느 경로든 실패해도 화면의 링크 텍스트는 그대로 남으므로 손으로 복사할 수 있다.
 */
export async function shareInvite(crewName: string, token: string): Promise<void> {
  const message = inviteMessage(crewName, token);
  if (Platform.OS !== "web") {
    try {
      await Share.share({ message });
      return;
    } catch {
      /* 사용자가 닫은 경우 포함 — 아래 복사로 폴백하지 않는다 */
      return;
    }
  }
  const nav = navigator as any;
  if (nav?.share) {
    try {
      await nav.share({ title: `${crewName} 초대`, text: message });
      return;
    } catch {
      /* 취소했거나 미지원 → 복사로 폴백 */
    }
  }
  const copied = await copyToClipboard(message);
  notify(
    copied ? "초대 문구를 복사했어요" : "복사에 실패했어요",
    copied ? "카톡방에 붙여넣기(⌘V) 하세요" : "아래 링크를 길게 눌러 직접 복사해주세요",
    copied ? "success" : "error",
  );
}

export async function copyInviteLink(token: string): Promise<void> {
  const copied = await copyToClipboard(inviteUrl(token));
  notify(
    copied ? "링크를 복사했어요" : "복사에 실패했어요",
    copied ? "카톡방에 붙여넣으면 초대장이 열려요" : "아래 링크를 길게 눌러 직접 복사해주세요",
    copied ? "success" : "error",
  );
}
