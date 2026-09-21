import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useState } from "react";
import { ScrollView, Text, TextInput, View } from "react-native";
import { Btn } from "../components";
import { Icon } from "../Icon";
import { notify, notifyError } from "../notify";
import { api } from "../api";
import { supabase } from "../supabase";
import { t, ui } from "../ui";

interface Preview {
  crew_name: string;
  inviter_name: string;
  member_count: number;
  used: boolean;
  expired: boolean;
}

/** 웹 현관: 카톡에 공유된 초대 링크의 첫 화면. 가치를 먼저 보여주고, 가입은 그 다음. */
export default function InviteScreen({ route, navigation }: any) {
  const { token } = route.params;
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [requested, setRequested] = useState(false);

  useEffect(() => {
    api.get<Preview>(`/invites/${token}`).then(setPreview).catch((e) => setError(e.message));
    (async () => {
      if (supabase) {
        const { data } = await supabase.auth.getSession();
        if (data.session) {
          setLoggedIn(true);
          return;
        }
      }
      setLoggedIn(!!(await AsyncStorage.getItem("userId"))); // dev 헤더 폴백
    })();
  }, [token]);

  const join = async () => {
    try {
      if (!loggedIn) {
        if (supabase) {
          // 실인증 모드: 초대장을 두고 로그인부터 (OTP 후 다시 이 링크로)
          navigation.navigate("Login");
          return;
        }
        if (!name.trim()) return;
        const user = await api.post<{ id: string }>("/users", { name: name.trim() });
        await AsyncStorage.setItem("userId", user.id);
        await api.post("/identity/verify"); // dev: 스텁 본인인증
      }
      // §29: 바로 멤버가 되지 않는다 — 초대한 분이 확인하고 받아줘야 한다
      await api.post<{ status: string; crew_name: string }>(`/invites/${token}/join`);
      setRequested(true);
    } catch (e: any) {
      notifyError(e);
    }
  };

  if (error) {
    return (
      <View style={{ flex: 1, backgroundColor: t.bg, alignItems: "center", justifyContent: "center", padding: 24 }}>
        <Text style={[ui.display, { fontSize: 26 }]}>with-care</Text>
        <Text style={{ fontSize: 14, color: t.sub, marginTop: 10, textAlign: "center", lineHeight: 21 }}>{error}</Text>
        <Btn label="처음 화면으로" tone="ghost" onPress={() => navigation.navigate("Landing")} />
      </View>
    );
  }

  if (!preview) {
    return (
      <View style={{ flex: 1, backgroundColor: t.bg, alignItems: "center", justifyContent: "center" }}>
        <Text style={{ fontSize: 13, color: t.sub }}>초대장을 여는 중…</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: t.bg, justifyContent: "center" }}>
      <View style={{ position: "absolute", top: -120, left: -90, width: 280, height: 280, borderRadius: 999, backgroundColor: t.mintTint }} />
      <View style={{ position: "absolute", bottom: -130, right: -100, width: 300, height: 300, borderRadius: 999, backgroundColor: t.lemonTint }} />

      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: 22 }}>
        <View style={{ width: "100%", maxWidth: 440, alignSelf: "center", gap: 16 }}>
          {/* 초대장 */}
          <View style={{ backgroundColor: t.card, borderWidth: 1, borderColor: t.border, borderRadius: 26, overflow: "hidden" }}>
            <View style={{ backgroundColor: t.mint, padding: 24 }}>
              <Text style={{ fontSize: 12, fontWeight: "700", color: "#DFF5EE", letterSpacing: 3 }}>초대장</Text>
              <Text style={[ui.display, { fontSize: 28, color: "#fff", marginTop: 6 }]}>{preview.crew_name}</Text>
              <Text style={{ fontSize: 13, color: "#DFF5EE", marginTop: 6 }}>
                {preview.inviter_name}님이 초대했어요 · 지금 {preview.member_count}집
              </Text>
            </View>

            <View style={{ padding: 22, gap: 16 }}>
              <Text style={{ fontSize: 15, color: t.ink, lineHeight: 23 }}>
                아이 돌봄을 서로 도와주는 모임이에요.{"\n"}
                <Text style={{ fontWeight: "700" }}>봐줄 수 있는 시간을 누르면</Text> 앱이 짝을 맞춰주고,
                누가 얼마나 봤는지도 대신 세어줍니다.
              </Text>

              <View style={{ gap: 10 }}>
                {[
                  { icon: "calendar" as const, text: "이번 주 되는 시간만 누르면 끝" },
                  { icon: "coins" as const, text: "누가 더 봐줬는지 앱이 기록해요" },
                  { icon: "shield" as const, text: "초대한 분이 확인해야 들어올 수 있어요" },
                  { icon: "camera" as const, text: "돌봄 사진은 이 모임 안에서만 보여요" },
                ].map((r) => (
                  <View key={r.text} style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                    <View style={{ width: 30, height: 30, borderRadius: 10, backgroundColor: t.mintTint, alignItems: "center", justifyContent: "center" }}>
                      <Icon name={r.icon} size={16} color={t.mintDeep} />
                    </View>
                    <Text style={{ flex: 1, fontSize: 13, color: t.sub, lineHeight: 19 }}>{r.text}</Text>
                  </View>
                ))}
              </View>

              {requested ? (
                <View style={{ backgroundColor: t.mintTint, borderRadius: 14, padding: 16, gap: 8 }}>
                  <Text style={{ fontSize: 15, fontWeight: "700", color: t.ink }}>신청했어요</Text>
                  <Text style={{ fontSize: 13, color: t.sub, lineHeight: 20 }}>
                    {preview.inviter_name}님이 확인하고 받아주시면 알림으로 알려드릴게요.
                    그때까지는 모임의 어떤 정보도 보이지 않아요.
                  </Text>
                  <Btn label="내 화면으로 가기" tone="soft" onPress={() => navigation.navigate("Home")} style={{ marginTop: 0 }} />
                </View>
              ) : preview.used || preview.expired ? (
                <View style={{ backgroundColor: t.coralTint, borderRadius: 14, padding: 14 }}>
                  <Text style={{ fontSize: 13, color: t.coralDeep, lineHeight: 20 }}>
                    {preview.used ? "이 초대 링크는 정원이 찼어요." : "기한이 지난 초대예요."} 초대한 분께 새 링크를 요청해주세요.
                  </Text>
                </View>
              ) : (
                <>
                  {!loggedIn && !supabase && (
                    <TextInput
                      style={ui.input}
                      placeholder="이름을 입력하고 신청하세요"
                      placeholderTextColor={t.sub}
                      value={name}
                      onChangeText={setName}
                    />
                  )}
                  <Btn label="합류 신청하기" onPress={join} style={{ marginTop: 0 }} />
                  <Text style={{ fontSize: 11, color: t.sub, textAlign: "center" }}>
                    신청하면 {preview.inviter_name}님이 확인 후 받아줘요 · 그 전까지 모임 정보는 보이지 않아요
                  </Text>
                </>
              )}
            </View>
          </View>

          <View style={{ alignItems: "center", gap: 6 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <View style={{ width: 26, height: 26, borderRadius: 9, backgroundColor: t.mint, alignItems: "center", justifyContent: "center" }}>
                <Icon name="heart" size={14} color="#fff" width={2.2} />
              </View>
              <Text style={[ui.display, { fontSize: 17 }]}>with-care</Text>
            </View>
            <Text style={{ fontSize: 12, color: t.sub }}>단톡방 옆에 사는 총무</Text>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}
