import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, View } from "react-native";
import { api, CrewView } from "../api";
import { Avatar, Btn, Columns, Page, PageHeader, Pill } from "../components";
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
          <Text style={ui.sectionTitle}>활성화 절차</Text>
          <View style={[ui.card, { backgroundColor: t.lemonTint, borderColor: "#F3E4BE", shadowOpacity: 0 }]}>
            <Text style={{ fontSize: 13, color: t.lemonDeep, lineHeight: 20 }}>
              세 단계를 마쳐야 보드가 열려요 — 포괄 합의(I2) → 규약 확정(I7) → 활성화.
              규약 없이 시작하는 크루는 만들지 않아요.
            </Text>
          </View>
          <Btn
            label="① 포괄 합의 (책임·사진·법정대리인)"
            onPress={act(() =>
              api.post(`/crews/${crewId}/consent`, {
                liability_ack: true,
                photo_consent: true,
                guardian_consent: true,
              }),
            )}
          />
          <Btn label="② 규약 확정" tone="soft" onPress={act(() => api.post(`/crews/${crewId}/charter/confirm`, {}))} />
          <Btn label="③ 크루 활성화" tone="deep" onPress={act(() => api.post(`/crews/${crewId}/activate`))} />
        </>
      )}

      <Text style={ui.sectionTitle}>이웃 초대</Text>
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
      <Text style={ui.sectionTitle}>우리 크루 규약</Text>
      {charter && (
        <View style={[ui.card, { backgroundColor: t.deep, borderColor: t.deep }]}>
          {[
            ["정산 모드", charter.settlement_mode],
            ["1크레딧(1시간)", `${charter.credit_price_krw.toLocaleString()}원`],
            ["호스트 사례", `${charter.host_fee_krw.toLocaleString()}원`],
            ["노쇼 벌금", `${charter.no_show_fine_krw.toLocaleString()}원`],
          ].map(([k, v]) => (
            <View key={k} style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 8 }}>
              <Text style={{ fontSize: 13, color: t.deepSub }}>{k}</Text>
              <Text style={{ fontSize: 13, color: "#fff", fontWeight: "700" }}>{v}</Text>
            </View>
          ))}
          <Text style={{ fontSize: 11, color: t.deepSub, marginTop: 4 }}>
            {charter.is_complete ? "확정됨 · 규약은 크루가 정하고 앱은 집행만 해요" : "미확정 — 확정해야 활성화돼요"}
          </Text>
        </View>
      )}

      <Text style={ui.sectionTitle}>노쇼·급취소 기록</Text>
      {badges.length === 0 ? (
        <Text style={ui.hint}>기록 없음 — 깨끗해요</Text>
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
        sub={`${active ? "활성 크루" : "규약 합의 중"} · ${crew.member_count}가구`}
        right={<Pill label={active ? "활성" : "합의 중"} tone={active ? "mint" : "lemon"} />}
      />
      <Columns left={mainCol} right={sideCol} />
    </Page>
  );
}
