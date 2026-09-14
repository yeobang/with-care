import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, Child, CrewView } from "../api";
import { Avatar, Btn, Columns, Empty, Note, Page, PageHeader, Pill } from "../components";
import { Icon } from "../Icon";
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
      <Text style={ui.sectionTitle}>내 모임</Text>
      {crews.length === 0 && (
        <Empty
          icon="users"
          title="아직 모임이 없어요"
          body={"친한 가족 3~6집과 함께 시작해요.\n모임을 만들고 링크를 카톡방에 붙이면 끝이에요."}
        />
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
              <Pill label={active ? "쓰는 중" : "준비 중"} tone={active ? "mint" : "lemon"} />
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10 }}>
              <Avatar id={c.id} label={c.name} size={26} />
              <Text style={{ fontSize: 13, color: t.sub }}>{c.member_count}집</Text>
              {!active && (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                  <Icon name="chevron" size={13} color={t.lemonDeep} />
                  <Text style={{ fontSize: 12, color: t.lemonDeep, fontWeight: "700" }}>눌러서 준비 마치기</Text>
                </View>
              )}
            </View>
          </TouchableOpacity>
        );
      })}

      <Text style={ui.sectionTitle}>모임 만들기</Text>
      <TextInput
        style={ui.input}
        placeholder="예: 아파트 놀이터 모임"
        placeholderTextColor={t.sub}
        value={crewName}
        onChangeText={setCrewName}
      />
      <Btn label="만들기" onPress={createCrew} />
      <Note icon="users">만들면 바로 다음 단계(규칙 정하기)로 안내해드려요. 혼자서도 먼저 만들어두고 나중에 초대할 수 있어요.</Note>

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
      <Text style={ui.sectionTitle}>우리 아이</Text>
      {children.length === 0 && (
        <Empty
          icon="heart"
          title="아이를 먼저 등록해주세요"
          body={"돌봄을 맡기려면 누구를 맡기는지 알아야 해요.\n이름과 태어난 달만 있으면 됩니다."}
        />
      )}
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
