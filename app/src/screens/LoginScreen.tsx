import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useState } from "react";
import { Linking, Platform, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, ApiError, IdentityMethod } from "../api";
import { enabledSocials, naverStartUrl, sendPhoneCode, signInWithSocial, Social, verifyPhoneCode } from "../authProviders";
import { LOCAL_TOKEN_KEY } from "../api";
import { Btn } from "../components";
import { notify } from "../notify";
import { supabase } from "../supabase";
import { t, ui } from "../ui";

type Mode = "signup" | "login" | "magic";

/**
 * P6 실인증 (Supabase Auth).
 * 기본은 이메일+비밀번호 회원가입/로그인 — 무료 플랜 메일 발송이 시간당 2통으로 묶여 있어
 * 메일 링크만으로는 실사용이 막힌다. 메일 링크는 "비밀번호 없이" 보조 경로로 남긴다.
 * supabase 미설정이면 dev 헤더 가입 폴백.
 */
export default function LoginScreen({ navigation }: any) {
  const [mode, setMode] = useState<Mode>("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [sentMail, setSentMail] = useState(false);
  const [name, setName] = useState("");
  const [needProfile, setNeedProfile] = useState(false);
  const [busy, setBusy] = useState(false);
  const [socials, setSocials] = useState<Social[]>([]);
  const [idMethod, setIdMethod] = useState<IdentityMethod["method"]>("stub");
  const [needPhone, setNeedPhone] = useState(false);
  const [phone, setPhone] = useState("");
  const [phoneCode, setPhoneCode] = useState("");
  const [phoneSent, setPhoneSent] = useState(false);

  const done = () => navigation.reset({ index: 0, routes: [{ name: "Home" }] });

  /** 로그인 성공 후: 프로필 있으면 홈, 없으면 이름 입력 단계로. */
  const ensureProfile = async () => {
    try {
      await api.get("/me");
      done();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setNeedProfile(true);
      else notify("오류", (e as Error).message);
    }
  };

  // 네이버 콜백으로 돌아온 경우: URL 조각의 토큰을 저장하고 이어간다
  useEffect(() => {
    if (Platform.OS !== "web") return;
    const hash = window.location.hash ?? "";
    const m = /token=([^&]+)/.exec(hash);
    if (!m) return;
    const signup = /signup=1/.test(hash);
    const nm = /name=([^&]*)/.exec(hash);
    (async () => {
      await AsyncStorage.setItem(LOCAL_TOKEN_KEY, decodeURIComponent(m[1]));
      window.history.replaceState(null, "", window.location.pathname);
      if (nm && nm[1]) setName(decodeURIComponent(nm[1]));
      if (signup) setNeedProfile(true);
      else await ensureProfile();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    enabledSocials().then(setSocials);
    api.get<IdentityMethod>("/identity/method").then((r) => setIdMethod(r.method)).catch(() => {});
  }, []);

  // 메일 링크·소셜 로그인으로 세션이 생긴 채 도착한 경우
  useEffect(() => {
    if (!supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) ensureProfile();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = (fn: () => Promise<void>) => async () => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      notify("오류", e?.message ?? "잠시 후 다시 시도해주세요");
    } finally {
      setBusy(false);
    }
  };

  const signUp = run(async () => {
    if (!supabase) return;
    if (!email.trim() || password.length < 8) {
      notify("입력 확인", "이메일과 8자 이상 비밀번호를 입력해주세요");
      return;
    }
    const { error } = await supabase.auth.signUp({ email: email.trim(), password });
    if (error) {
      const dup = /already|exists|registered/i.test(error.message);
      notify(dup ? "이미 가입된 이메일" : "가입 실패", dup ? "로그인 탭에서 로그인해주세요" : error.message);
      if (dup) setMode("login");
      return;
    }
    await ensureProfile();
  });

  const signIn = run(async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    if (error) {
      notify("로그인 실패", /invalid/i.test(error.message) ? "이메일 또는 비밀번호를 확인해주세요" : error.message);
      return;
    }
    await ensureProfile();
  });

  const sendMagic = run(async () => {
    if (!supabase || !email.trim()) return;
    const { error } = await supabase.auth.signInWithOtp({ email: email.trim() });
    if (error) notify("메일 발송 실패", error.message);
    else setSentMail(true);
  });

  const verifyCode = run(async () => {
    if (!supabase) return;
    const { error } = await supabase.auth.verifyOtp({ email: email.trim(), token: code.trim(), type: "email" });
    if (error) notify("확인 실패", error.message);
    else await ensureProfile();
  });

  const createProfile = run(async () => {
    if (!name.trim()) return;
    const user = await api.post<{ id: string }>("/users", { name: name.trim() });
    if (!supabase) await AsyncStorage.setItem("userId", user.id); // dev 헤더 흐름
    try {
      await api.post("/identity/verify"); // 수단은 서버가 고른다 (stub/email/phone)
      done();
    } catch (e) {
      if (idMethod === "phone") setNeedPhone(true); // 휴대폰 인증 단계로
      else throw e;
    }
  });

  const requestPhone = run(async () => {
    const p = phone.trim().replace(/[^0-9+]/g, "");
    if (!p) return;
    const { error } = await sendPhoneCode(p.startsWith("+") ? p : `+82${p.replace(/^0/, "")}`);
    if (error) notify("문자 발송 실패", error.message);
    else setPhoneSent(true);
  });

  const confirmPhone = run(async () => {
    const p = phone.trim().replace(/[^0-9+]/g, "");
    const { error } = await verifyPhoneCode(p.startsWith("+") ? p : `+82${p.replace(/^0/, "")}`, phoneCode.trim());
    if (error) {
      notify("인증 실패", error.message);
      return;
    }
    await api.post("/identity/verify"); // 서버가 JWT의 phone_confirmed_at을 확인한다
    done();
  });

  const devMode = !supabase;
  const showProfileStep = devMode || needProfile;

  const tab = (m: Mode, label: string) => (
    <TouchableOpacity
      key={m}
      style={{
        flex: 1,
        height: 42,
        borderRadius: 12,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: mode === m ? t.mintTint : "transparent",
      }}
      onPress={() => {
        setMode(m);
        setSentMail(false);
      }}
    >
      <Text style={{ fontSize: 14, fontWeight: mode === m ? "700" : "400", color: mode === m ? t.mintDeep : t.sub }}>
        {label}
      </Text>
    </TouchableOpacity>
  );

  return (
    <View style={{ flex: 1, backgroundColor: t.bg, justifyContent: "center" }}>
      <View style={{ position: "absolute", top: -130, right: -110, width: 320, height: 320, borderRadius: 999, backgroundColor: t.mintTint }} />
      <View style={{ position: "absolute", top: 160, left: -100, width: 220, height: 220, borderRadius: 999, backgroundColor: t.lemonTint }} />
      <View style={{ position: "absolute", bottom: -120, right: 40, width: 260, height: 260, borderRadius: 999, backgroundColor: t.coralTint, opacity: 0.6 }} />

      <View style={{ width: "100%", maxWidth: 440, alignSelf: "center", paddingHorizontal: 24, gap: 26 }}>
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
          {needPhone ? (
            <>
              <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub }}>휴대폰 본인인증</Text>
              <Text style={ui.hint}>아이를 맡고 맡기려면 본인인증이 필요해요 (I1)</Text>
              <TextInput
                style={ui.input}
                placeholder="010-1234-5678"
                placeholderTextColor={t.sub}
                keyboardType="phone-pad"
                value={phone}
                onChangeText={setPhone}
                editable={!phoneSent}
              />
              {!phoneSent ? (
                <Btn label={busy ? "보내는 중…" : "인증 문자 받기"} onPress={requestPhone} />
              ) : (
                <>
                  <TextInput
                    style={ui.input}
                    placeholder="문자로 받은 6자리"
                    placeholderTextColor={t.sub}
                    keyboardType="number-pad"
                    value={phoneCode}
                    onChangeText={setPhoneCode}
                  />
                  <Btn label={busy ? "확인 중…" : "인증 완료"} onPress={confirmPhone} />
                  <TouchableOpacity onPress={() => setPhoneSent(false)}>
                    <Text style={[ui.hint, { textAlign: "center" }]}>번호 다시 입력</Text>
                  </TouchableOpacity>
                </>
              )}
            </>
          ) : showProfileStep ? (
            <>
              <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub }}>
                {devMode ? "이름을 알려주세요" : "거의 다 됐어요 — 이름만 알려주세요"}
              </Text>
              <TextInput style={ui.input} placeholder="이름" placeholderTextColor={t.sub} value={name} onChangeText={setName} />
              <Btn label={busy ? "처리 중…" : devMode ? "시작하기 (dev)" : "프로필 만들기"} onPress={createProfile} />
              {devMode && <Text style={ui.hint}>dev 모드: Supabase 환경변수 없음 — 헤더 인증 폴백</Text>}
            </>
          ) : (
            <>
              <View style={{ flexDirection: "row", backgroundColor: t.bg, borderRadius: 14, padding: 4, marginBottom: 12 }}>
                {tab("signup", "회원가입")}
                {tab("login", "로그인")}
                {tab("magic", "메일 링크")}
              </View>

              {socials.length > 0 && (
                <View style={{ gap: 8, marginBottom: 10 }}>
                  {socials.map((sp) => (
                    <TouchableOpacity
                      key={sp.id}
                      style={{
                        height: 52,
                        borderRadius: 16,
                        backgroundColor: sp.bg,
                        borderWidth: sp.id === "google" ? 1.5 : 0,
                        borderColor: t.border,
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                      onPress={run(async () => {
                        if (sp.id === "naver") {
                          // 우리 서버가 처리 — 콜백이 토큰을 URL로 돌려준다
                          if (Platform.OS === "web") window.location.href = naverStartUrl();
                          else Linking.openURL(naverStartUrl());
                          return;
                        }
                        const { error } = await signInWithSocial(sp.id);
                        if (error) notify("로그인 실패", error.message);
                      })}
                    >
                      <Text style={{ fontSize: 15, fontWeight: "700", color: sp.fg }}>{sp.label}</Text>
                    </TouchableOpacity>
                  ))}
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: 4 }}>
                    <View style={{ flex: 1, height: 1, backgroundColor: t.border }} />
                    <Text style={{ fontSize: 12, color: t.sub }}>또는 이메일로</Text>
                    <View style={{ flex: 1, height: 1, backgroundColor: t.border }} />
                  </View>
                </View>
              )}

              <TextInput
                style={ui.input}
                placeholder="이메일"
                placeholderTextColor={t.sub}
                autoCapitalize="none"
                autoComplete="email"
                keyboardType="email-address"
                value={email}
                onChangeText={setEmail}
              />

              {mode !== "magic" && (
                <TextInput
                  style={ui.input}
                  placeholder={mode === "signup" ? "비밀번호 (8자 이상)" : "비밀번호"}
                  placeholderTextColor={t.sub}
                  secureTextEntry
                  autoCapitalize="none"
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  value={password}
                  onChangeText={setPassword}
                />
              )}

              {mode === "signup" && (
                <>
                  <Btn label={busy ? "가입 중…" : "회원가입"} onPress={signUp} />
                  <Text style={ui.hint}>메일 확인 절차 없이 바로 시작해요. 아이 인계는 본인인증을 거쳐야 열려요.</Text>
                </>
              )}

              {mode === "login" && (
                <>
                  <Btn label={busy ? "로그인 중…" : "로그인"} onPress={signIn} />
                  <Text style={ui.hint}>비밀번호가 기억나지 않으면 “메일 링크”로 들어올 수 있어요</Text>
                </>
              )}

              {mode === "magic" && (
                <>
                  {!sentMail ? (
                    <>
                      <Btn label={busy ? "보내는 중…" : "로그인 링크 받기"} tone="soft" onPress={sendMagic} />
                      <Text style={ui.hint}>비밀번호 없이 메일 링크로 들어와요 · 메일 발송은 시간당 2통까지</Text>
                    </>
                  ) : (
                    <>
                      <Text style={{ fontSize: 14, color: t.ink, lineHeight: 21, marginTop: 4 }}>
                        {email} 로 메일을 보냈어요.{"\n"}
                        <Text style={{ fontWeight: "700", color: t.mintDeep }}>로그인 링크</Text>를 누르면 이 화면에서 이어져요.
                      </Text>
                      <TextInput
                        style={ui.input}
                        placeholder="메일에 코드가 있다면 입력"
                        placeholderTextColor={t.sub}
                        keyboardType="number-pad"
                        value={code}
                        onChangeText={setCode}
                      />
                      <Btn label="코드로 확인" tone="soft" onPress={verifyCode} />
                      <TouchableOpacity onPress={() => setSentMail(false)}>
                        <Text style={[ui.hint, { textAlign: "center" }]}>이메일 다시 입력</Text>
                      </TouchableOpacity>
                    </>
                  )}
                </>
              )}
            </>
          )}
        </View>

        <Text style={{ fontSize: 12, color: t.sub, textAlign: "center", lineHeight: 18 }}>
          본인인증과 크루 초대 없이는 아이 인계가 일어나지 않아요
        </Text>
      </View>
    </View>
  );
}
