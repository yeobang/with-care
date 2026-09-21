import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TouchableOpacity, View } from "react-native";
import { api, CrewView, JoinRequest, Post, timeAgo } from "../api";
import { Avatar, Btn, Columns, NavBar, Note, Page, PageHeader, Pill, Steps } from "../components";
import { InviteCard, JoinRequests } from "../InviteCard";
import { SkeletonCard } from "../pickers";
import { notifyError } from "../notify";
import { t, ui } from "../ui";

interface Charter {
  settlement_mode: string;
  credit_price_krw: number;
  host_fee_krw: number;
  no_show_fine_krw: number;
  is_complete: boolean;
}

interface IncidentBadge {
  user_id: string;
  count: number;
  fine_krw_total: number;
}

/** 모임이 실제로 굴러가려면 3집부터 (§29). */
const MIN_HOUSEHOLDS = 3;

export default function CrewScreen({ route, navigation }: any) {
  const { crewId } = route.params;
  const [crew, setCrew] = useState<CrewView | null>(null);
  const [charter, setCharter] = useState<Charter | null>(null);
  const [requests, setRequests] = useState<JoinRequest[]>([]);
  const [badges, setBadges] = useState<IncidentBadge[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);

  const load = useCallback(() => {
    api.get<CrewView>(`/crews/${crewId}`).then(setCrew).catch(() => {});
    api.get<Charter>(`/crews/${crewId}/charter`).then(setCharter).catch(() => {});
    api.get<IncidentBadge[]>(`/crews/${crewId}/incidents`).then(setBadges).catch(() => {});
    api.get<Post[]>(`/posts?scope=crew&crew_id=${crewId}&limit=5`).then(setPosts).catch(() => {});
    api.get<JoinRequest[]>(`/crews/${crewId}/join-requests`).then(setRequests).catch(() => {});
  }, [crewId]);
  useFocusEffect(load);

  const act = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      notifyError(e);
    }
  };

  if (!crew)
    return (
      <Page wide nav={<NavBar navigation={navigation} />}>
        <SkeletonCard lines={3} />
        <SkeletonCard lines={2} />
      </Page>
    );
  const active = crew.status === "active";

  // §29: 사람이 모이기 전에는 '규칙'이 아니라 '초대'가 이 화면의 주인공이다
  const needsPeople = crew.member_count < MIN_HOUSEHOLDS;

  const mainCol = (
    <View>
      <JoinRequests crewId={crewId} requests={requests} onDecided={load} />

      {needsPeople && (
        <InviteCard crewId={crewId} crewName={crew.name} memberCount={crew.member_count} />
      )}

      {active ? (
        <>
          <Text style={ui.sectionTitle}>무엇을 할까요?</Text>
          <Btn label="주간 보드 열기" onPress={() => navigation.navigate("Board", { crewId, name: crew.name })} />
          <Btn label="장부·정산 열기" tone="soft" onPress={() => navigation.navigate("Ledger", { crewId, name: crew.name })} />
          <Btn label="시터 공구 열기" tone="ghost" onPress={() => navigation.navigate("Sitter", { crewId, name: crew.name })} />
          <Btn
            label="모임 단체방 열기"
            tone="soft"
            onPress={act(async () => {
              const r = await api.post<{ id: string }>(`/crews/${crewId}/chat`);
              navigation.navigate("ChatRoom", { roomId: r.id, title: crew.name });
            })}
          />
        </>
      ) : (
        <>
          <Text style={ui.sectionTitle}>시작 전 준비 (3단계)</Text>
          <Steps items={["약속 확인", "규칙 정하기", "시작하기"]} current={charter?.is_complete ? 2 : 0} />
          <Note icon="shield" tone="warn">
            서로 얼굴 붉힐 일을 미리 없애는 단계예요. 책임 범위·사진·간식 같은 걸 먼저 정해두면,
            나중에 “그건 말 안 했잖아”가 생기지 않아요.
          </Note>
          <Btn
            label="① 약속 확인하기 (책임·사진·보호자 동의)"
            onPress={act(() =>
              api.post(`/crews/${crewId}/consent`, {
                liability_ack: true,
                photo_consent: true,
                guardian_consent: true,
              }),
            )}
          />
          <Btn label="② 우리 규칙 정하기" tone="soft" onPress={act(() => api.post(`/crews/${crewId}/charter/confirm`, {}))} />
          <Btn label="③ 시작하기" tone="deep" onPress={act(() => api.post(`/crews/${crewId}/activate`))} />
        </>
      )}

      {!needsPeople && (
        <>
          <Text style={ui.sectionTitle}>이웃 초대하기</Text>
          <InviteCard crewId={crewId} crewName={crew.name} memberCount={crew.member_count} compact />
        </>
      )}
    </View>
  );

  const sideCol = (
    <View>
      <Text style={ui.sectionTitle}>우리 규칙</Text>
      {charter && (
        <View style={[ui.card, { backgroundColor: t.deep, borderColor: t.deep }]}>
          {[
            ["정산 방식", charter.settlement_mode === "credit" ? "기록 + 월말 정산" : charter.settlement_mode === "rotation" ? "번갈아 하기" : "기록만"],
            ["1시간 돌봄의 값", `${charter.credit_price_krw.toLocaleString()}원`],
            ["집 빌려준 사례비", `${charter.host_fee_krw.toLocaleString()}원`],
            ["갑자기 못 왔을 때", `${charter.no_show_fine_krw.toLocaleString()}원`],
          ].map(([k, v]) => (
            <View key={k} style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 8 }}>
              <Text style={{ fontSize: 13, color: t.deepSub }}>{k}</Text>
              <Text style={{ fontSize: 13, color: "#fff", fontWeight: "700" }}>{v}</Text>
            </View>
          ))}
          <Text style={{ fontSize: 11, color: t.deepSub, marginTop: 4 }}>
            {charter.is_complete ? "정해졌어요 · 규칙은 여러분이 정하고 앱은 지키기만 해요" : "아직 안 정했어요 — 정해야 시작할 수 있어요"}
          </Text>
        </View>
      )}

      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 22 }}>
        <Text style={[ui.sectionTitle, { marginTop: 0, marginBottom: 0 }]}>모임 이야기</Text>
        <TouchableOpacity onPress={() => navigation.navigate("Write", { scope: "crew", crewId })}>
          <Text style={{ fontSize: 13, fontWeight: "700", color: t.mintDeep }}>글쓰기</Text>
        </TouchableOpacity>
      </View>
      {posts.length === 0 ? (
        <Text style={ui.hint}>공지나 후기를 남겨보세요 — 이 모임 멤버만 볼 수 있어요</Text>
      ) : (
        posts.map((p) => (
          <TouchableOpacity key={p.id} style={ui.card} onPress={() => navigation.navigate("Post", { postId: p.id })}>
            <Text style={ui.cardTitle}>{p.title}</Text>
            <Text numberOfLines={1} style={{ fontSize: 13, color: t.sub, marginTop: 5 }}>{p.body}</Text>
            <Text style={{ fontSize: 11, color: t.sub, marginTop: 8 }}>
              {p.author.name} · {timeAgo(p.created_at)} · 댓글 {p.comment_count}
            </Text>
          </TouchableOpacity>
        ))
      )}

      <Text style={ui.sectionTitle}>약속 못 지킨 기록</Text>
      {badges.length === 0 ? (
        <Text style={ui.hint}>아직 없어요 — 모두 잘 지키고 있어요</Text>
      ) : (
        <>
          {badges.map((b) => (
            <View key={b.user_id} style={[ui.card, { flexDirection: "row", alignItems: "center", gap: 12 }]}>
              <Avatar id={b.user_id} label="?" size={36} />
              <View style={{ flex: 1 }}>
                <Text style={ui.cardTitle}>이웃 ({b.user_id.slice(0, 6)})</Text>
                <Text style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>
                  {b.count}회 · 안내된 벌금 {b.fine_krw_total.toLocaleString()}원
                </Text>
              </View>
              <Pill label={`${b.count}회`} tone="coral" />
            </View>
          ))}
          <Text style={ui.hint}>반복은 배지로 투명하게 보여요. 벌금은 규약 안내일 뿐 앱이 걷지 않아요.</Text>
        </>
      )}
    </View>
  );

  return (
    <Page wide nav={<NavBar navigation={navigation} crewId={crewId} crewName={crew.name} active="crew" />}>
      <PageHeader
        title={crew.name}
        sub={
          needsPeople
            ? `${crew.member_count}집 · ${MIN_HOUSEHOLDS - crew.member_count}집 더 모이면 시작할 수 있어요`
            : `${active ? "쓰는 중" : "준비 중"} · ${crew.member_count}집`
        }
        right={
          <Pill
            label={needsPeople ? "사람 모으는 중" : active ? "쓰는 중" : "준비 중"}
            tone={needsPeople ? "coral" : active ? "mint" : "lemon"}
          />
        }
      />
      <Columns left={mainCol} right={sideCol} />
    </Page>
  );
}
