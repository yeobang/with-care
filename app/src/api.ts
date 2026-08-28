import AsyncStorage from "@react-native-async-storage/async-storage";

const BASE = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const userId = await AsyncStorage.getItem("userId");
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(userId ? { "X-User-Id": userId } : {}),
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
};

export async function uploadSessionPhoto(sessionId: string, uri: string): Promise<void> {
  const userId = await AsyncStorage.getItem("userId");
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
    headers: userId ? { "X-User-Id": userId } : {},
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

export interface CareSession {
  id: string;
  caregiver_id: string;
  date: string;
  start_hour: number;
  end_hour: number;
  handoff_started_at: string | null;
  handoff_ended_at: string | null;
}
