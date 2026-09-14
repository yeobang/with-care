import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, View } from "react-native";
import { api, CrewView } from "../api";
import { Avatar, Btn, Columns, Empty, Note, Page, PageHeader, Pill, Steps } from "../components";
import { notify } from "../notify";
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

const WEB_ORIGIN = "https://with-care-web.fly.dev";

export default function CrewScreen({ route, navigation }: any) {
  const { crewId } = route.params;
  const [crew, setCrew] = useState<CrewView | null>(null);
  const [charter, setCharter] = useState<Charter | null>(null);
  const [invite, setInvite] = useState<string | null>(null);
  const [badges, setBadges] = useState<IncidentBadge[]>([]);

  const load = useCallback(() => {
    api.get<CrewView>(`/crews/${crewId}`).then(setCrew).catch(() => {});
    api.get<Charter>(`/crews/${crewId}/charter`).then(setCharter).catch(() => {});
    api.get<IncidentBadge[]>(`/crews/${crewId}/incidents`).then(setBadges).catch(() => {});
  }, [crewId]);
  useFocusEffect(load);

  const act = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      notify(e.invariant ? `가드레일 ${e.invariant}` : "오류", e.message);
    }
  };

  if (!crew) return <Page />;
  const active = crew.status === "active";

  const mainCol = (
    <View>
      {active ? (
        <>
          <Text style={ui.sectionTitle}>무엇을 할까요?</Text>
          <Btn label="주간 보드 열기" onPress={() => navigation.navigate("Board", { crewId, name: crew.name })} />
          <Btn label="장부·정산 열기" tone="soft" onPress={() => navigation.navigate("Ledger", { crewId, name: crew.name })} />
          <Btn label="시터 공구 열기" tone="ghost" onPress={() => navigation.navigate("Sitter", { crewId, name: crew.name })} />
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

      <Text style={ui.sectionTitle}>이웃 초대하기</Text>
      <Btn
        label="초대 링크 만들기"
        tone={active ? "soft" : "ghost"}
        onPress={act(async () => {
          const r = await api.post<{ token: string }>(`/crews/${crewId}/invites`);
          setInvite(r.token);
        })}
      />
      {invite && (
        <View style={ui.card}>
          <Text selectable style={{ fontSize: 13, fontWeight: "600", color: t.mintDeep }}>
            {`${WEB_ORIGIN}/invite/${invite}`}
          </Text>
          <Text style={ui.hint}>카톡방에 붙여넣으면 초대장이 열려요 · 7일 유효, 1회용</Text>
        </View>
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
    <Page wide>
      <PageHeader
        title={crew.name}
        sub={`${active ? "쓰는 중" : "준비 중"} · ${crew.member_count}집`}
        right={<Pill label={active ? "쓰는 중" : "준비 중"} tone={active ? "mint" : "lemon"} />}
      />
      <Columns left={mainCol} right={sideCol} />
    </Page>
  );
}
