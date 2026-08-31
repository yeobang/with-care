import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import {
  Alert,
  FlatList,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
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
      await api.post("/crews", { name: crewName.trim() });
      setCrewName("");
      load();
    } catch (e: any) {
      Alert.alert("오류", e.message);
    }
  };

  const join = async () => {
    if (!inviteToken.trim()) return;
    try {
      await api.post(`/invites/${inviteToken.trim()}/join`);
      setInviteToken("");
      load();
    } catch (e: any) {
      Alert.alert("합류 실패", e.message);
    }
  };

  const addChild = async () => {
    if (!childName.trim() || !/^\d{4}-\d{2}$/.test(childBirth)) {
      Alert.alert("입력 확인", "아이 이름과 생년월(YYYY-MM)을 입력해주세요");
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
      Alert.alert("오류", e.message);
    }
  };

  return (
    <View style={ui.screen}>
      <Text style={ui.sectionTitle}>내 크루</Text>
      <FlatList
        data={crews}
        keyExtractor={(c) => c.id}
        ListEmptyComponent={<Text style={ui.hint}>아직 크루가 없어요</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={ui.card}
            onPress={() => navigation.navigate("Crew", { crewId: item.id, name: item.name })}
          >
            <Text style={{ fontWeight: "700" }}>{item.name}</Text>
            <Text style={ui.hint}>
              {item.status === "active" ? "활성" : "규약 합의 중"} · {item.member_count}가구
            </Text>
          </TouchableOpacity>
        )}
      />

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

      <Text style={ui.sectionTitle}>내 아이 ({children.length})</Text>
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
    </View>
  );
}
