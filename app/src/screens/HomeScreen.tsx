import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, Child, CrewView } from "../api";
import { Avatar, Btn, Columns, Page, PageHeader, Pill } from "../components";
import { notify } from "../notify";
import { registerPush } from "../push";
import { t, ui, useLayout } from "../ui";

export default function HomeScreen({ navigation }: any) {
  const [crews, setCrews] = useState<CrewView[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [crewName, setCrewName] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [childName, setChildName] = useState("");
  const [childBirth, setChildBirth] = useState("");
  const { isWide } = useLayout();

  const load = useCallback(() => {
    api.get<CrewView[]>("/my/crews").then(setCrews).catch(() => {});
    api.get<Child[]>("/my/children").then(setChildren).catch(() => {});
  }, []);
  useFocusEffect(load);

  useEffect(() => {
    registerPush(); // best-effort
  }, []);

  const createCrew = async () => {
    if (!crewName.trim()) return;
    try {
      const crew = await api.post<CrewView>("/crews", { name: crewName.trim() });
      setCrewName("");
      navigation.navigate("Crew", { crewId: crew.id, name: crew.name });
    } catch (e: any) {
      notify("오류", e.message);
    }
  };

  const join = async () => {
    if (!inviteToken.trim()) return;
    const token = inviteToken.trim().split("/").pop() ?? ""; // 링크를 붙여넣어도 되게
    try {
      const crew = await api.post<CrewView>(`/invites/${token}/join`, undefined);
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

  const crewList = (
    <View>
      <Text style={ui.sectionTitle}>내 크루</Text>
      {crews.length === 0 && (
        <Text style={ui.hint}>아직 크루가 없어요 — 아래에서 만들거나, 초대 링크로 합류하세요</Text>
      )}
      {crews.map((c) => {
        const active = c.status === "active";
        return (
          <TouchableOpacity
            key={c.id}
            style={ui.card}
            onPress={() => navigation.navigate("Crew", { crewId: c.id, name: c.name })}
          >
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={ui.cardTitle}>{c.name}</Text>
              <Pill label={active ? "활성" : "규약 합의 중"} tone={active ? "mint" : "lemon"} />
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10 }}>
              <Avatar id={c.id} label={c.name} size={26} />
              <Text style={{ fontSize: 13, color: t.sub }}>{c.member_count}가구</Text>
              {!active && <Text style={{ fontSize: 12, color: t.lemonDeep, fontWeight: "700" }}>· 눌러서 이어가기</Text>}
            </View>
          </TouchableOpacity>
        );
      })}

      <Text style={ui.sectionTitle}>크루 만들기</Text>
      <TextInput style={ui.input} placeholder="크루 이름" placeholderTextColor={t.sub} value={crewName} onChangeText={setCrewName} />
      <Btn label="만들기" onPress={createCrew} />

      <Text style={ui.sectionTitle}>초대받았나요?</Text>
      <TextInput
        style={ui.input}
        placeholder="초대 링크 또는 코드"
        placeholderTextColor={t.sub}
        value={inviteToken}
        onChangeText={setInviteToken}
      />
      <Btn label="합류하기" tone="soft" onPress={join} />
    </View>
  );

  const childPanel = (
    <View>
      <Text style={ui.sectionTitle}>내 아이 ({children.length})</Text>
      {children.map((c) => (
        <View key={c.id} style={[ui.card, { flexDirection: "row", alignItems: "center", gap: 12 }]}>
          <Avatar id={c.id} label={c.name} size={40} />
          <View>
            <Text style={ui.cardTitle}>{c.name}</Text>
            <Text style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>{c.birth_year_month}</Text>
          </View>
        </View>
      ))}
      <View style={{ flexDirection: "row", gap: 8 }}>
        <TextInput
          style={[ui.input, { flex: 1 }]}
          placeholder="이름"
          placeholderTextColor={t.sub}
          value={childName}
          onChangeText={setChildName}
        />
        <TextInput
          style={[ui.input, { width: 120 }]}
          placeholder="2022-05"
          placeholderTextColor={t.sub}
          value={childBirth}
          onChangeText={setChildBirth}
        />
      </View>
      <Btn label="아이 등록" tone="soft" onPress={addChild} />
      <Text style={ui.hint}>돌봄을 맡기려면 아이가 등록돼 있어야 해요 (보드의 “돌봄 필요” 칸)</Text>
    </View>
  );

  return (
    <Page wide>
      <PageHeader title="안녕하세요" sub="이번 주 돌봄, 제가 챙길게요" />
      {isWide ? <Columns left={crewList} right={childPanel} /> : (
        <View>
          {crewList}
          {childPanel}
        </View>
      )}
    </Page>
  );
}
