import { supabase } from "./supabase";

const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Supabase에 실제로 켜져 있는 소셜 로그인만 버튼으로 노출한다.
 * (/auth/v1/settings 는 공개 엔드포인트 — 켜진 provider 목록을 돌려준다)
 * → 대시보드에서 Google·Kakao 키를 넣는 순간 코드 변경 없이 버튼이 생긴다.
 */
export type Social = { id: "google" | "kakao" | "naver"; label: string; bg: string; fg: string };

const KNOWN: Social[] = [
  { id: "kakao", label: "카카오로 계속하기", bg: "#FEE500", fg: "#191600" },
  { id: "naver", label: "네이버로 계속하기", bg: "#03C75A", fg: "#FFFFFF" },
  { id: "google", label: "Google로 계속하기", bg: "#FFFFFF", fg: "#1F1F1F" },
];

export const NAVER: Social = KNOWN[1];

export async function enabledSocials(): Promise<Social[]> {
  const out: Social[] = [];
  const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
  const key = process.env.EXPO_PUBLIC_SUPABASE_KEY;
  // Supabase가 처리하는 제공자 (카카오·구글)
  if (url && key) {
    try {
      const res = await fetch(`${url}/auth/v1/settings`, { headers: { apikey: key } });
      if (res.ok) {
        const ext = (await res.json())?.external ?? {};
        out.push(...KNOWN.filter((s) => s.id !== "naver" && ext[s.id] === true));
      }
    } catch {
      // 조회 실패 시 조용히 숨김 — 이메일 경로는 살아 있다
    }
  }
  // 네이버는 우리 서버가 처리 (Supabase 미지원)
  try {
    const res = await fetch(`${API_BASE}/auth/providers`);
    if (res.ok && (await res.json())?.naver === true) out.push(NAVER);
  } catch {
    // 무시
  }
  return out;
}

/** 네이버는 우리 서버의 시작 URL로 이동한다 (브라우저 리다이렉트) */
export function naverStartUrl(): string {
  return `${API_BASE}/auth/naver/start`;
}

/** 카카오·구글은 Supabase가 처리한다 (네이버는 naverStartUrl 경로). */
export async function signInWithSocial(provider: "google" | "kakao", redirectTo?: string) {
  if (!supabase) return { error: { message: "인증이 설정되지 않았어요" } };
  return supabase.auth.signInWithOAuth({ provider, options: { redirectTo } });
}

/** 전화 OTP — 본인인증(I1) 수단. Supabase에 SMS 제공자(Twilio 등)가 설정돼야 동작. */
export async function sendPhoneCode(phone: string) {
  if (!supabase) return { error: { message: "인증이 설정되지 않았어요" } };
  return supabase.auth.updateUser({ phone }); // 로그인된 사용자에 전화 추가 → SMS 발송
}

export async function verifyPhoneCode(phone: string, token: string) {
  if (!supabase) return { error: { message: "인증이 설정되지 않았어요" } };
  return supabase.auth.verifyOtp({ phone, token, type: "phone_change" });
}
