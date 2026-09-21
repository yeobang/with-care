import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, Child, CrewView, JoinRequest } from "../api";
import { Avatar, Btn, Columns, Empty, NavBar, Note, Page, PageHeader, Pill, StatTiles } from "../components";
import { InviteCard, JoinRequests } from "../InviteCard";
import { TabBar } from "../TabBar";
import { MonthPicker, SkeletonCard } from "../pickers";
import { Icon } from "../Icon";
import { notify, notifyError } from "../notify";
import { registerPush } from "../push";
import { t, ui, useLayout } from "../ui";

/** 모임이 실제로 굴러가려면 3집부터 (§29). 그 전까지 화면의 주인공은 '초대'다. */
const MIN_HOUSEHOLDS = 3;

export default function HomeScreen({ navigation }: any) {
  const [crews, setCrews] = useState<CrewView[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [pending, setPending] = useState<Record<string, JoinRequest[]>>({});
  const [crewName, setCrewName] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [childName, setChildName] = useState("");
  const [childBirth, setChildBirth] = useState("");
  const [childContact, setChildContact] = useState("");
  const [loading, setLoading] = useState(true);
  const { isWide } = useLayout();

  const load = useCallback(() => {
    Promise.all([
      api
        .get<CrewView[]>("/my/crews")
        .then(async (cs) => {
          setCrews(cs);
          const entries = await Promise.all(
            cs.map(async (c) => {
              const reqs = await api
                .get<JoinRequest[]>(`/crews/${c.id}/join-requests`)
                .catch(() => [] as JoinRequest[]);
              return [c.id, reqs] as const;
            }),
          );
          setPending(Object.fromEntries(entries));
        })
        .catch(() => {}),
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
      // §29: 만든 직후의 할 일은 '규칙'이 아니라 '초대'다. 모임 화면이 그렇게 열린다.
      navigation.navigate("Crew", { crewId: crew.id, name: crew.name });
    } catch (e: any) {
      notifyError(e);
    }
  };

  const join = async () => {
    if (!inviteToken.trim()) return;
    const token = inviteToken.trim().split("/").pop() ?? ""; // 링크를 붙여넣어도 되게
    try {
      const r = await api.post<{ crew_name: string }>(`/invites/${token}/join`, undefined);
      setInviteToken("");
      notify(
        "신청했어요",
        `${r.crew_name}에 합류 신청을 보냈어요. 초대한 분이 확인하면 알려드릴게요.`,
        "success",
      );
      load();
    } catch (e: any) {
      notifyError(e);
    }
  };

  const addChild = async () => {
    if (!childName.trim() || !/^\d{4}-\d{2}$/.test(childBirth)) {
      notify("조금만 더", "아이 이름과 태어난 달을 채워주세요", "error");
      return;
    }
    // 비상연락처는 실제로 연락이 닿아야 하는 값이다 — 임의 기본값을 넣지 않는다
    const contact = childContact.replace(/[^\d]/g, "");
    if (contact.length < 9) {
      notify("연락처를 확인해주세요", "돌봄 중 급한 일이 생기면 이 번호로 연락해요", "error");
      return;
    }
    try {
      await api.post("/my/children", {
        name: childName.trim(),
        birth_year_month: childBirth,
        emergency_contact: childContact.trim(),
      });
      setChildName("");
      setChildBirth("");
      setChildContact("");
      notify("등록했어요", `${childName.trim()} 아이를 추가했어요`, "success");
      load();
    } catch (e: any) {
      notifyError(e);
    }
  };

  const hasChild = children.length > 0;
  const hasCrew = crews.length > 0;
  const hasActive = crews.some((c) => c.status === "active");
  const invited = crews.some((c) => c.member_count >= 2);
  const allDone = hasChild && hasCrew && hasActive && invited;
  // 아직 사람이 덜 모인 모임 — 화면의 맨 위를 차지한다
  const needsPeople = crews.find((c) => c.member_count < MIN_HOUSEHOLDS);

  const checklist = !loading && !allDone && (
    <View style={[ui.card, { backgroundColor: t.card }]}>
      <Text style={{ fontSize: 15, fontWeight: "700", color: t.ink }}>여기까지 하면 시작돼요</Text>
      {[
        { done: hasCrew, label: "모임 만들기", hint: "이름만 정하면 30초" },
        { done: invited, label: "단톡방에 초대 링크 붙이기", hint: "제일 중요한 한 걸음" },
        { done: hasActive, label: "규칙 정하고 시작하기", hint: "모임 화면에서 3단계" },
        { done: hasChild, label: "우리 아이 등록하기", hint: "이름·태어난 달·비상연락처" },
      ].map((it, i) => (
        <View key={it.label} style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: i === 0 ? 12 : 10 }}>
          <View
            style={{
              width: 22,
              height: 22,
              borderRadius: 999,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: it.done ? t.mint : t.bg,
              borderWidth: it.done ? 0 : 1.5,
              borderColor: t.border,
            }}
          >
            {it.done ? (
              <Icon name="check" size={13} color="#fff" width={2.6} />
            ) : (
              <Text style={{ fontSize: 11, fontWeight: "700", color: t.sub }}>{i + 1}</Text>
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Text
              style={{
                fontSize: 14,
                fontWeight: it.done ? "400" : "700",
                color: it.done ? t.sub : t.ink,
                textDecorationLine: it.done ? "line-through" : "none",
              }}
            >
              {it.label}
            </Text>
            {!it.done && <Text style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>{it.hint}</Text>}
          </View>
        </View>
      ))}
    </View>
  );

  /** 모임이 하나도 없는 사람에게 보여주는 단 하나의 행동. */
  const firstRun = (
    <View style={[ui.card, { backgroundColor: t.mintTint, borderColor: "#CFEBE2", shadowOpacity: 0 }]}>
      <Text style={[ui.display, { fontSize: 22 }]}>모임부터 만들어요</Text>
      <Text style={{ fontSize: 14, color: t.sub, marginTop: 8, lineHeight: 22 }}>
        이름만 정하면 바로 초대 링크가 나와요.{"\n"}
        늘 쓰는 단톡방에 그 링크를 붙이면 준비 끝이에요.
      </Text>
      <TextInput
        style={[ui.input, { backgroundColor: t.card, marginTop: 14 }]}
        placeholder="예: 아파트 놀이터 모임"
        placeholderTextColor={t.sub}
        value={crewName}
        onChangeText={setCrewName}
        onSubmitEditing={createCrew}
        returnKeyType="done"
      />
      <Btn label="모임 만들고 초대 링크 받기" onPress={createCrew} />
      <Text style={{ fontSize: 12, color: t.sub, marginTop: 10, lineHeight: 18 }}>
        3집부터 서로 시간을 맞바꿀 수 있어요. 아이 등록·규칙은 사람이 모인 뒤에 해도 돼요.
      </Text>
    </View>
  );

  const crewList = (
    <View>
      {Object.entries(pending).map(([crewId, rs]) =>
        rs.length > 0 ? (
          <JoinRequests key={crewId} crewId={crewId} requests={rs} onDecided={load} />
        ) : null,
      )}

      {!loading && !hasCrew && firstRun}

      {!loading && needsPeople && (
        <InviteCard
          crewId={needsPeople.id}
          crewName={needsPeople.name}
          memberCount={needsPeople.member_count}
        />
      )}

      {checklist}

      <Text style={ui.sectionTitle}>내 모임</Text>
      {loading && <SkeletonCard lines={2} />}
      {!loading && crews.length === 0 && (
        <Empty
          icon="users"
          title="아직 모임이 없어요"
          body={"친한 가족 3~6집과 함께 시작해요.\n위에서 모임을 만들면 초대 링크가 바로 나와요."}
        />
      )}
      {crews.map((c) => {
        const active = c.status === "active";
        const waiting = c.member_count < MIN_HOUSEHOLDS;
        return (
          <TouchableOpacity
            key={c.id}
            style={ui.card}
            onPress={() => navigation.navigate("Crew", { crewId: c.id, name: c.name })}
          >
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={ui.cardTitle}>{c.name}</Text>
              <Pill
                label={waiting ? "사람 모으는 중" : active ? "쓰는 중" : "준비 중"}
                tone={waiting ? "coral" : active ? "mint" : "lemon"}
              />
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
              <Avatar id={c.id} label={c.name} size={26} />
              <Text style={{ fontSize: 13, color: t.sub }}>
                {c.member_count}집{waiting ? ` · ${MIN_HOUSEHOLDS - c.member_count}집 더 필요해요` : ""}
              </Text>
              {!active && !waiting && (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                  <Icon name="chevron" size={13} color={t.lemonDeep} />
                  <Text style={{ fontSize: 12, color: t.lemonDeep, fontWeight: "700" }}>눌러서 준비 마치기</Text>
                </View>
              )}
            </View>
          </TouchableOpacity>
        );
      })}

      {hasCrew && (
        <>
          <Text style={ui.sectionTitle}>모임 하나 더 만들기</Text>
          <TextInput
            style={ui.input}
            placeholder="예: 아파트 놀이터 모임"
            placeholderTextColor={t.sub}
            value={crewName}
            onChangeText={setCrewName}
          />
          <Btn label="만들기" tone="ghost" onPress={createCrew} />
        </>
      )}

      <Text style={ui.sectionTitle}>초대받았나요?</Text>
      <TextInput
        style={ui.input}
        placeholder="초대 링크 또는 코드"
        placeholderTextColor={t.sub}
        value={inviteToken}
        onChangeText={setInviteToken}
      />
      <Btn label="합류 신청하기" tone="soft" onPress={join} />
      <Note icon="shield">
        신청하면 초대한 분이 확인 후 받아줘요. 그 전까지는 모임의 어떤 정보도 보이지 않아요.
      </Note>
    </View>
  );

  const childPanel = (
    <View>
      <Text style={ui.sectionTitle}>우리 아이</Text>
      {children.length === 0 && (
        <Empty
          icon="heart"
          title={hasCrew ? "아이를 등록해주세요" : "사람이 모이면 등록해요"}
          body={"돌봄을 맡기려면 누구를 맡기는지 알아야 해요.\n이름·태어난 달·비상연락처만 있으면 됩니다."}
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
      <TextInput
        style={ui.input}
        placeholder="비상연락처 (예: 010-1234-5678)"
        placeholderTextColor={t.sub}
        keyboardType="phone-pad"
        value={childContact}
        onChangeText={setChildContact}
      />
      <Text style={ui.hint}>돌봄 중 급한 일이 생겼을 때 돌봐주는 분이 거는 번호예요.</Text>
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
        <PageHeader
          title="안녕하세요"
          sub={hasCrew ? "이번 주 돌봄, 제가 챙길게요" : "모임을 만들고 단톡방에 링크만 붙이면 시작돼요"}
        />
        {summary}
        {isWide ? (
          <Columns left={crewList} right={childPanel} />
        ) : (
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
