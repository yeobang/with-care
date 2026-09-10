import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useState } from "react";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, ApiError } from "../api";
import { Btn } from "../components";
import { notify } from "../notify";
import { supabase } from "../supabase";
import { t, ui } from "../ui";

/** P6 실인증: 이메일 링크/코드(Supabase Auth). supabase 미설정이면 dev 헤더 가입 폴백. */
export default function LoginScreen({ navigation }: any) {
  const [step, setStep] = useState<"email" | "otp" | "profile">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");

  const done = () => navigation.reset({ index: 0, routes: [{ name: "Home" }] });

  const ensureProfile = async () => {
    try {
      await api.get("/me");
      done();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setStep("profile");
      else notify("오류", (e as Error).message);
    }
  };

  // 메일 링크로 이미 세션이 생긴 채 도착한 경우 → 프로필 단계로
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) ensureProfile();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendOtp = async () => {
    if (!supabase || !email.trim()) return;
    const { error } = await supabase.auth.signInWithOtp({ email: email.trim() });
    if (error) notify("오류", error.message);
    else setStep("otp");
  };

  const verifyOtp = async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "email" });
    if (error) notify("오류", error.message);
    else await ensureProfile();
  };

  const createProfile = async () => {
    if (!name.trim()) return;
    try {
      const user = await api.post<{ id: string }>("/users", { name: name.trim() });
      if (!supabase) await AsyncStorage.setItem("userId", user.id);
      await api.post("/identity/verify");
      done();
    } catch (e: any) {
      notify("오류", e.message);
    }
  };

  const devMode = !supabase;

  return (
    <View style={{ flex: 1, backgroundColor: t.bg, justifyContent: "center" }}>
      {/* 배경 파스텔 블롭 */}
      <View style={{ position: "absolute", top: -130, right: -110, width: 320, height: 320, borderRadius: 999, backgroundColor: t.mintTint }} />
      <View style={{ position: "absolute", top: 160, left: -100, width: 220, height: 220, borderRadius: 999, backgroundColor: t.lemonTint }} />
      <View style={{ position: "absolute", bottom: -120, right: 40, width: 260, height: 260, borderRadius: 999, backgroundColor: t.coralTint, opacity: 0.6 }} />

      <View style={{ width: "100%", maxWidth: 440, alignSelf: "center", paddingHorizontal: 24, gap: 30 }}>
        <View style={{ alignItems: "center", gap: 10 }}>
          <View
            style={{
              width: 72,
              height: 72,
              borderRadius: 26,
              backgroundColor: t.mint,
              alignItems: "center",
              justifyContent: "center",
              transform: [{ rotate: "-6deg" }],
              shadowColor: t.mint,
              shadowOpacity: 0.38,
              shadowRadius: 20,
              shadowOffset: { width: 0, height: 10 },
            }}
          >
            <Text style={{ fontSize: 32 }}>🧡</Text>
          </View>
          <Text style={[ui.display, { fontSize: 40, marginTop: 6 }]}>with-care</Text>
          <Text style={{ fontSize: 15, color: t.sub }}>단톡방 옆에 사는 총무</Text>
        </View>

        <View style={ui.card}>
          {devMode || step === "profile" ? (
            <>
              <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub, marginBottom: 4 }}>
                {devMode ? "이름을 알려주세요" : "거의 다 됐어요"}
              </Text>
              <TextInput style={ui.input} placeholder="이름" placeholderTextColor={t.sub} value={name} onChangeText={setName} />
              <Btn label={devMode ? "시작하기 (dev)" : "프로필 만들기"} onPress={createProfile} />
              {devMode && <Text style={ui.hint}>dev 모드: Supabase 환경변수 없음 — 헤더 인증 폴백</Text>}
            </>
          ) : step === "email" ? (
            <>
              <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub, marginBottom: 4 }}>이메일로 시작</Text>
              <TextInput
                style={ui.input}
                placeholder="parent@example.com"
                placeholderTextColor={t.sub}
                autoCapitalize="none"
                keyboardType="email-address"
                value={email}
                onChangeText={setEmail}
              />
              <Btn label="메일로 시작하기" onPress={sendOtp} />
              <Text style={ui.hint}>메일 속 로그인 링크를 누르면 이 화면에서 이어져요</Text>
            </>
          ) : (
            <>
              <Text style={{ fontSize: 14, color: t.ink, lineHeight: 21 }}>
                {email} 로 메일을 보냈어요.{"\n"}
                <Text style={{ fontWeight: "700", color: t.mintDeep }}>로그인 링크</Text>를 누르면 이 화면에서 이어져요.
              </Text>
              <Text style={ui.hint}>메일에 인증 코드가 보이면 여기 입력해도 돼요</Text>
              <TextInput
                style={ui.input}
                placeholder="인증 코드"
                placeholderTextColor={t.sub}
                keyboardType="number-pad"
                value={code}
                onChangeText={setCode}
              />
              <Btn label="코드로 확인" tone="soft" onPress={verifyOtp} />
              <TouchableOpacity onPress={sendOtp}>
                <Text style={[ui.hint, { textAlign: "center" }]}>메일 다시 받기</Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        <Text style={{ fontSize: 12, color: t.sub, textAlign: "center" }}>
          본인인증과 크루 초대 없이는 아이 인계가 일어나지 않아요
        </Text>
      </View>
    </View>
  );
}
