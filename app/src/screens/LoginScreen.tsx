import AsyncStorage from "@react-native-async-storage/async-storage";
import { useState } from "react";
import { Alert, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, ApiError } from "../api";
import { supabase } from "../supabase";
import { ui } from "../ui";

/** P6 실인증: 이메일 OTP(Supabase Auth). supabase 미설정이면 dev 헤더 가입 폴백. */
export default function LoginScreen({ navigation }: any) {
  const [step, setStep] = useState<"email" | "otp" | "profile">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");

  const done = () => navigation.reset({ index: 0, routes: [{ name: "Home" }] });

  /** 로그인 후: 프로필 있으면 홈, 없으면(signup_required) 이름 입력으로. */
  const ensureProfile = async () => {
    try {
      await api.get("/me");
      done();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setStep("profile");
      else Alert.alert("오류", (e as Error).message);
    }
  };

  const sendOtp = async () => {
    if (!supabase || !email.trim()) return;
    const { error } = await supabase.auth.signInWithOtp({ email: email.trim() });
    if (error) Alert.alert("오류", error.message);
    else setStep("otp");
  };

  const verifyOtp = async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.verifyOtp({
      email: email.trim(),
      token: code.trim(),
      type: "email",
    });
    if (error) Alert.alert("오류", error.message);
    else await ensureProfile();
  };

  const createProfile = async () => {
    if (!name.trim()) return;
    try {
      const user = await api.post<{ id: string }>("/users", { name: name.trim() });
      if (!supabase) await AsyncStorage.setItem("userId", user.id); // dev 헤더 흐름
      await api.post("/identity/verify"); // 본인인증(스텁 어댑터) — PASS류 확보 시 교체
      done();
    } catch (e: any) {
      Alert.alert("오류", e.message);
    }
  };

  const devMode = !supabase;
  return (
    <View style={ui.container}>
      <Text style={ui.title}>with-care</Text>
      <Text style={ui.subtitle}>단톡방 옆에 사는 총무</Text>
      {devMode || step === "profile" ? (
        <>
          <TextInput
            style={[ui.input, { width: "100%" }]}
            placeholder="이름"
            value={name}
            onChangeText={setName}
          />
          <TouchableOpacity style={ui.primaryBtn} onPress={createProfile}>
            <Text style={ui.primaryBtnText}>{devMode ? "시작하기 (dev)" : "프로필 만들기"}</Text>
          </TouchableOpacity>
          {devMode && (
            <Text style={ui.hint}>* dev 모드: Supabase 환경변수 없음 — 헤더 인증 폴백</Text>
          )}
        </>
      ) : step === "email" ? (
        <>
          <TextInput
            style={[ui.input, { width: "100%" }]}
            placeholder="이메일"
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />
          <TouchableOpacity style={ui.primaryBtn} onPress={sendOtp}>
            <Text style={ui.primaryBtnText}>인증 코드 받기</Text>
          </TouchableOpacity>
        </>
      ) : (
        <>
          <Text style={ui.hint}>{email} 로 보낸 코드를 입력해주세요</Text>
          <TextInput
            style={[ui.input, { width: "100%" }]}
            placeholder="123456"
            keyboardType="number-pad"
            value={code}
            onChangeText={setCode}
          />
          <TouchableOpacity style={ui.primaryBtn} onPress={verifyOtp}>
            <Text style={ui.primaryBtnText}>확인</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={sendOtp}>
            <Text style={ui.hint}>코드 다시 받기</Text>
          </TouchableOpacity>
        </>
      )}
    </View>
  );
}
