import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import {
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { notify } from "../notify";
import { api, Child, CrewView } from "../api";
import { registerPush } from "../push";
import { ui } from "../ui";

export default function HomeScreen({ navigation }: any) {
  const [crews, setCrews] = useState<CrewView[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [crewName, setCrewName] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [childName, setChildName] = useState("");
  const [childBirth, setChildBirth] = useState("");

  const load = useCallback(() => {
    api.get<CrewView[]>("/my/crews").then(setCrews).catch(() => {});
    api.get<Child[]>("/my/children").then(setChildren).catch(() => {});
  }, []);
  useFocusEffect(load);

  useEffect(() => {
    registerPush(); // 푸시 토큰 등록 (best-effort — 실패해도 무시)
  }, []);

  const createCrew = async () => {
    if (!crewName.trim()) return;
    try {
      const crew = await api.post<CrewView>("/crews", { name: crewName.trim() });
      setCrewName("");
      // 생성 즉시 크루 화면으로 — 다음 할 일(합의→규약→활성화)이 거기 있다
      navigation.navigate("Crew", { crewId: crew.id, name: crew.name });
    } catch (e: any) {
      notify("오류", e.message);
    }
  };

  const join = async () => {
    if (!inviteToken.trim()) return;
    try {
      const crew = await api.post<CrewView>(`/invites/${inviteToken.trim()}/join`, undefined);
      setInviteToken("");
      navigation.navigate("Crew", { crewId: crew.id, name: crew.name });
    } catch (e: any) {
      notify("합류 실패", e.message);
    }
  };

  const addChild = async () => {
    if (!childName.trim() || !/^\d{4}-\d{2}$/.test(childBirth)) {
      notify("입력 확인", "아이 이름과 생년월(YYYY-MM)을 입력해주세요");
      return;
    }
    try {
      await api.post("/my/children", {
        name: childName.trim(),
        birth_year_month: childBirth,
        emergency_contact: "010-0000-0000",
      });
      setChildName("");
      setChildBirth("");
      load();
    } catch (e: any) {
      notify("오류", e.message);
    }
  };

  return (
    <ScrollView style={ui.screen} contentContainerStyle={{ paddingBottom: 40 }}>
      <Text style={ui.sectionTitle}>내 크루</Text>
      {crews.length === 0 && (
        <Text style={ui.hint}>아직 크루가 없어요 — 아래에서 만들거나, 초대 코드로 합류하세요</Text>
      )}
      {crews.map((c) => (
        <TouchableOpacity
          key={c.id}
          style={ui.card}
          onPress={() => navigation.navigate("Crew", { crewId: c.id, name: c.name })}
        >
          <Text style={{ fontWeight: "700", fontSize: 16 }}>{c.name}</Text>
          <Text style={ui.hint}>
            {c.status === "active" ? "✅ 활성" : "📝 규약 합의 중 — 눌러서 이어가기"} · {c.member_count}가구
          </Text>
        </TouchableOpacity>
      ))}

      <Text style={ui.sectionTitle}>내 아이 ({children.length})</Text>
      {children.map((c) => (
        <View key={c.id} style={ui.card}>
          <Text style={{ fontWeight: "700" }}>{c.name}</Text>
          <Text style={ui.hint}>{c.birth_year_month}</Text>
        </View>
      ))}
      <View style={ui.row}>
        <TextInput
          style={[ui.input, { flex: 1, marginRight: 8 }]}
          placeholder="이름"
          value={childName}
          onChangeText={setChildName}
        />
        <TextInput
          style={[ui.input, { width: 110 }]}
          placeholder="2022-05"
          value={childBirth}
          onChangeText={setChildBirth}
        />
      </View>
      <TouchableOpacity style={ui.primaryBtn} onPress={addChild}>
        <Text style={ui.primaryBtnText}>아이 등록</Text>
      </TouchableOpacity>
      <Text style={ui.hint}>돌봄을 맡기려면 아이가 등록돼 있어야 해요 (보드의 &quot;돌봄 필요&quot; 칸)</Text>

      <Text style={ui.sectionTitle}>크루 만들기</Text>
      <TextInput style={ui.input} placeholder="크루 이름" value={crewName} onChangeText={setCrewName} />
      <TouchableOpacity style={ui.primaryBtn} onPress={createCrew}>
        <Text style={ui.primaryBtnText}>만들기</Text>
      </TouchableOpacity>

      <Text style={ui.sectionTitle}>초대 코드로 합류</Text>
      <TextInput style={ui.input} placeholder="초대 토큰" value={inviteToken} onChangeText={setInviteToken} />
      <TouchableOpacity style={ui.primaryBtn} onPress={join}>
        <Text style={ui.primaryBtnText}>합류하기</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
