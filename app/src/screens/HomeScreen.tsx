import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, Child, CrewView } from "../api";
import { Avatar, Btn, Columns, Empty, NavBar, Note, Page, PageHeader, Pill, StatTiles } from "../components";
import { TabBar } from "../TabBar";
import { MonthPicker, SkeletonCard } from "../pickers";
import { Icon } from "../Icon";
import { notify, notifyError } from "../notify";
import { registerPush } from "../push";
import { t, ui, useLayout } from "../ui";

export default function HomeScreen({ navigation }: any) {
  const [crews, setCrews] = useState<CrewView[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [crewName, setCrewName] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [childName, setChildName] = useState("");
  const [childBirth, setChildBirth] = useState("");
  const [loading, setLoading] = useState(true);
  const { isWide } = useLayout();

  const load = useCallback(() => {
    Promise.all([
      api.get<CrewView[]>("/my/crews").then(setCrews).catch(() => {}),
      api.get<Child[]>("/my/children").then(setChildren).catch(() => {}),
    ]).finally(() => setLoading(false));
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
      notifyError(e);
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
      notifyError(e);
    }
  };

  const addChild = async () => {
    if (!childName.trim() || !/^\d{4}-\d{2}$/.test(childBirth)) {
      notify("조금만 더", "아이 이름과 태어난 달을 채워주세요", "error");
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
      notify("등록했어요", `${childName.trim()} 아이를 추가했어요`, "success");
      load();
    } catch (e: any) {
      notifyError(e);
    }
  };

  // 처음 들어온 사람이 "뭘 해야 하지"를 묻지 않게 — 남은 할 일만 보여준다
  const hasChild = children.length > 0;
  const hasCrew = crews.length > 0;
  const hasActive = crews.some((c) => c.status === "active");
  const allDone = hasChild && hasCrew && hasActive;

  const checklist = !loading && !allDone && (
    <View style={[ui.card, { backgroundColor: t.mintTint, borderColor: "#CFEBE2", shadowOpacity: 0 }]}>
      <Text style={{ fontSize: 15, fontWeight: "700", color: t.ink }}>시작하기</Text>
      <Text style={{ fontSize: 12, color: t.sub, marginTop: 4, marginBottom: 12 }}>
        세 가지만 하면 이번 주부터 쓸 수 있어요
      </Text>
      {[
        { done: hasChild, label: "우리 아이 등록하기", hint: "이름과 태어난 달만" },
        { done: hasCrew, label: "모임 만들거나 합류하기", hint: "친한 가족 3~6집" },
        { done: hasActive, label: "규칙 정하고 시작하기", hint: "모임 화면에서 3단계" },
      ].map((it) => (
        <View key={it.label} style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <View
            style={{
              width: 22,
              height: 22,
              borderRadius: 999,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: it.done ? t.mint : t.card,
              borderWidth: it.done ? 0 : 1.5,
              borderColor: t.border,
            }}
          >
            {it.done && <Icon name="check" size={13} color="#fff" width={2.6} />}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: it.done ? "400" : "700", color: it.done ? t.sub : t.ink, textDecorationLine: it.done ? "line-through" : "none" }}>
              {it.label}
            </Text>
            {!it.done && <Text style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>{it.hint}</Text>}
          </View>
        </View>
      ))}
    </View>
  );

  const crewList = (
    <View>
      {checklist}
      <Text style={ui.sectionTitle}>내 모임</Text>
      {loading && <SkeletonCard lines={2} />}
      {!loading && crews.length === 0 && (
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
      <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
        <TextInput
          style={[ui.input, { flex: 1, minWidth: 140 }]}
          placeholder="이름"
          placeholderTextColor={t.sub}
          value={childName}
          onChangeText={setChildName}
        />
        <View style={{ width: 190 }}>
          <MonthPicker value={childBirth} onChange={setChildBirth} />
        </View>
      </View>
      <Btn label="아이 등록" tone="soft" onPress={addChild} />
    </View>
  );

  const activeCrews = crews.filter((c) => c.status === "active").length;
  const summary = allDone && (
    <StatTiles
      items={[
        { label: "우리 모임", value: `${crews.length}개`, note: `${activeCrews}개 사용 중`, tone: "mint" },
        { label: "우리 아이", value: `${children.length}명`, note: "정보는 내 정보에서 수정", tone: "lemon" },
        { label: "지금 할 일", value: "보드 확인", note: "이번 주 되는 시간을 눌러주세요", tone: "coral" },
      ]}
    />
  );

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
    <Page wide nav={<NavBar navigation={navigation} />}>
      <PageHeader title="안녕하세요" sub="이번 주 돌봄, 제가 챙길게요" />
      {summary}
      {isWide ? <Columns left={crewList} right={childPanel} /> : (
        <View>
          {crewList}
          {childPanel}
        </View>
      )}
    </Page>
    <TabBar navigation={navigation} active="home" />
    </View>
  );
}
