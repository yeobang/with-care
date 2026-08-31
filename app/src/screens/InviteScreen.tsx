import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useState } from "react";
import { Alert, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api } from "../api";
import { supabase } from "../supabase";
import { ui } from "../ui";

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

  useEffect(() => {
    api.get<Preview>(`/invites/${token}`).then(setPreview).catch((e) => setError(e.message));
    AsyncStorage.getItem("userId").then((id) => setLoggedIn(!!id));
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
      const crew = await api.post<{ id: string; name: string }>(`/invites/${token}/join`);
      navigation.reset({
        index: 1,
        routes: [{ name: "Home" }, { name: "Crew", params: { crewId: crew.id, name: crew.name } }],
      });
    } catch (e: any) {
      Alert.alert(e.invariant ? `가드레일 ${e.invariant}` : "합류 실패", e.message);
    }
  };

  if (error) {
    return (
      <View style={ui.container}>
        <Text style={ui.title}>with-care</Text>
        <Text style={ui.subtitle}>{error}</Text>
      </View>
    );
  }
  if (!preview) return <View style={ui.container} />;

  return (
    <View style={ui.container}>
      <Text style={ui.subtitle}>초대장</Text>
      <Text style={ui.title}>{preview.crew_name}</Text>
      <Text style={{ marginTop: 12, textAlign: "center" }}>
        {preview.inviter_name}님이 초대했어요 · 현재 {preview.member_count}가구
      </Text>
      {preview.used || preview.expired ? (
        <Text style={ui.hint}>
          {preview.used ? "이미 사용된 초대예요." : "기한이 지난 초대예요."} 새 초대를 요청해주세요.
        </Text>
      ) : (
        <>
          {!loggedIn && !supabase && (
            <TextInput
              style={[ui.input, { width: "100%" }]}
              placeholder="이름을 입력하면 바로 합류돼요"
              value={name}
              onChangeText={setName}
            />
          )}
          <TouchableOpacity style={ui.primaryBtn} onPress={join}>
            <Text style={ui.primaryBtnText}>크루 합류하기</Text>
          </TouchableOpacity>
        </>
      )}
      <Text style={ui.hint}>이 화면은 초대장에 담긴 최소 정보만 보여줘요. 나머지는 합류 후에.</Text>
    </View>
  );
}
