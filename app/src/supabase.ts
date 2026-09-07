import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { Platform } from "react-native";

const url = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
const key = process.env.EXPO_PUBLIC_SUPABASE_KEY ?? ""; // publishable 키 (클라이언트 안전)

/** 환경변수 없으면 null — dev 헤더 인증 폴백 (api.ts). 경계 룰: Auth 외 용도로 쓰지 않는다. */
export const supabase: SupabaseClient | null =
  url && key
    ? createClient(url, key, {
        auth: {
          storage: AsyncStorage,
          persistSession: true,
          autoRefreshToken: true,
          // 웹: 메일의 로그인 링크 클릭 시 URL 해시에서 세션 회수
          // (무료 플랜은 메일 템플릿 수정 불가 → 코드 대신 링크가 온다)
          detectSessionInUrl: Platform.OS === "web",
        },
      })
    : null;
