import AsyncStorage from "@react-native-async-storage/async-storage";
import { supabase } from "./supabase";

const BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * 인증 헤더 우선순위:
 * 1) Supabase 세션 (이메일·카카오·구글)
 * 2) 자체 발급 토큰 (네이버 — Supabase 미지원이라 우리 서버가 서명)
 * 3) dev 헤더 (X-User-Id)
 */
export const LOCAL_TOKEN_KEY = "authToken";

async function authHeaders(): Promise<Record<string, string>> {
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) return { Authorization: `Bearer ${token}` };
  }
  const local = await AsyncStorage.getItem(LOCAL_TOKEN_KEY);
  if (local) return { Authorization: `Bearer ${local}` };
  const userId = await AsyncStorage.getItem("userId");
  return userId ? { "X-User-Id": userId } : {};
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public invariant?: string,
  ) {
    super(detail);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(res.status, data.detail ?? "요청 실패", data.invariant);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
};

export async function uploadSessionPhoto(sessionId: string, uri: string): Promise<void> {
  const form = new FormData();
  if (uri.startsWith("data:") || uri.startsWith("blob:")) {
    // 웹: picker가 data/blob URI를 줌
    const blob = await (await fetch(uri)).blob();
    form.append("file", new File([blob], "photo.jpg", { type: blob.type || "image/jpeg" }));
  } else {
    // 네이티브: 파일 URI
    form.append("file", { uri, name: "photo.jpg", type: "image/jpeg" } as unknown as Blob);
  }
  const res = await fetch(`${BASE}/sessions/${sessionId}/photos`, {
    method: "POST",
    headers: await authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail ?? "업로드 실패", data.invariant);
  }
}

// --- 타입 (api 응답) ---

export interface CrewView {
  id: string;
  name: string;
  status: string;
  charter_complete: boolean;
  member_count: number;
}

export interface Child {
  id: string;
  name: string;
  birth_year_month: string;
}

export interface Slot {
  id: string;
  user_id: string;
  kind: "available" | "need";
  start_hour: number;
  end_hour: number;
  child_id: string | null;
}

export interface AssignmentChild {
  child_id: string;
  child_name: string;
  guardian_id: string;
  guardian_confirmed: boolean;
}

export interface Assignment {
  id: string;
  caregiver_id: string;
  date: string;
  start_hour: number;
  end_hour: number;
  status: string;
  children: AssignmentChild[];
}

export interface SitterQuoteFamily {
  guardian_id: string;
  confirmed: boolean;
}

export interface SitterQuote {
  id: string;
  sitter_user_id: string;
  hourly_krw: number;
  surge: boolean;
  total_krw: number;
  per_family_krw: number;
  status: string;
  families: SitterQuoteFamily[];
}

export interface SitterRequest {
  id: string;
  date: string;
  start_hour: number;
  end_hour: number;
  status: string;
  child_count: number;
  quotes: SitterQuote[];
}

export interface CareSession {
  id: string;
  caregiver_id: string;
  date: string;
  start_hour: number;
  end_hour: number;
  handoff_started_at: string | null;
  handoff_ended_at: string | null;
  canceled_at: string | null;
}

export interface IdentityMethod {
  method: "stub" | "email" | "phone";
}

export interface AppNotification {
  id: string;
  crew_id: string | null;
  title: string;
  body: string;
  created_at: string;
  read: boolean;
}

/** "3시간 전" 같은 상대 시간 — 목록에서 절대시각보다 읽기 쉽다 */
export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "방금";
  if (m < 60) return `${m}분 전`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}일 전`;
  return iso.slice(0, 10);
}

export async function signOut() {
  const { supabase } = await import("./supabase");
  try {
    await supabase?.auth.signOut();
  } catch {
    // 무시 — 아래에서 로컬 흔적을 지운다
  }
  const AsyncStorage = (await import("@react-native-async-storage/async-storage")).default;
  await AsyncStorage.multiRemove([LOCAL_TOKEN_KEY, "userId"]);
}
