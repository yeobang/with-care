import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Linking, Text, View } from "react-native";
import { api } from "../api";
import { Avatar, Btn, Columns, Page, PageHeader, Pill } from "../components";
import { notify } from "../notify";
import { t, ui } from "../ui";

interface Settlement {
  id: string;
  month: string;
  from_user: string;
  to_user: string;
  amount_krw: number;
  amount_credits: number; // 0 = 호스트 사례 (§24-2)
  status: string;
  unsettled: boolean;
}

function currentMonth(): string {
  return new Date().toISOString().slice(0, 7);
}

export default function LedgerScreen({ route }: any) {
  const { crewId } = route.params;
  const [myId, setMyId] = useState<string | null>(null);
  const [balances, setBalances] = useState<Record<string, number>>({});
  const [settlements, setSettlements] = useState<Settlement[]>([]);

  useEffect(() => {
    api.get<{ id: string }>("/me").then((u) => setMyId(u.id)).catch(() => {});
  }, []);

  const load = useCallback(() => {
    api.get<Record<string, number>>(`/crews/${crewId}/ledger`).then(setBalances).catch(() => {});
    api.get<Settlement[]>(`/crews/${crewId}/settlements`).then(setSettlements).catch(() => {});
  }, [crewId]);
  useFocusEffect(load);

  const guard = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      notify(e.invariant ? `가드레일 ${e.invariant}` : "오류", e.message);
    }
  };

  const unsettled = settlements.filter((s) => s.unsettled);
  const mine = myId ? balances[myId] ?? 0 : 0;
  const maxAbs = Math.max(1, ...Object.values(balances).map((v) => Math.abs(v)));

  const balanceCol = (
    <View>
      <View style={[ui.card, { backgroundColor: t.deep, borderColor: t.deep, padding: 24 }]}>
        <Text style={{ fontSize: 13, color: t.deepSub }}>내 크레딧</Text>
        <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 8, marginTop: 4 }}>
          <Text style={[ui.display, { fontSize: 44, color: "#7FD8BE" }]}>{mine > 0 ? `+${mine}` : mine}</Text>
          <Text style={{ fontSize: 14, color: t.deepSub, marginBottom: 8 }}>아이·시간</Text>
        </View>
        <Text style={{ fontSize: 12, color: "#7E958D", marginTop: 4, lineHeight: 18 }}>
          {mine > 0
            ? `돌봐준 시간이 맡긴 시간보다 ${mine} 많아요`
            : mine < 0
              ? `맡긴 시간이 ${-mine} 많아요`
              : "지금은 균형이 맞아요"}
          {"\n"}장부 합계는 언제나 0 (제로섬)
        </Text>
      </View>

      <Text style={ui.sectionTitle}>가구별 잔액</Text>
      {Object.keys(balances).length === 0 ? (
        <Text style={ui.hint}>아직 기록이 없어요 — 세션이 끝나면 자동으로 쌓여요</Text>
      ) : (
        <View style={ui.card}>
          {Object.entries(balances).map(([uid, bal]) => {
            const pos = bal >= 0;
            const frac = Math.abs(bal) / maxAbs;
            return (
              <View key={uid} style={{ flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <Text style={{ width: 76, fontSize: 14, fontWeight: uid === myId ? "700" : "400", color: t.ink }}>
                  {uid === myId ? "나" : `이웃 ${uid.slice(0, 4)}`}
                </Text>
                <View
                  style={{
                    flex: 1,
                    height: 12,
                    borderRadius: 999,
                    backgroundColor: t.bg,
                    flexDirection: "row",
                    justifyContent: pos ? "flex-start" : "flex-end",
                    overflow: "hidden",
                  }}
                >
                  <View
                    style={{
                      width: `${Math.round(frac * 100)}%`,
                      backgroundColor: pos ? t.mint : t.coral,
                      borderRadius: 999,
                    }}
                  />
                </View>
                <Text style={{ width: 40, textAlign: "right", fontWeight: "700", color: pos ? t.mintDeep : t.coralDeep }}>
                  {pos ? `+${bal}` : bal}
                </Text>
              </View>
            );
          })}
          <Text style={{ fontSize: 12, color: t.sub }}>막대가 오른쪽이면 돌봄을 더 받은 가정이에요</Text>
        </View>
      )}
    </View>
  );

  const settleCol = (
    <View>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 22 }}>
        <Text style={[ui.sectionTitle, { marginTop: 0, marginBottom: 0 }]}>이번 달 정산</Text>
        {unsettled.length > 0 && <Pill label={`미정산 ${unsettled.length}건`} tone="coral" />}
      </View>

      <Btn
        label={`${currentMonth()} 정산 계산하기`}
        tone="ghost"
        onPress={guard(() => api.post(`/crews/${crewId}/settlements/${currentMonth()}/compute`))}
      />

      {settlements.length === 0 && <Text style={ui.hint}>아직 정산 제안이 없어요</Text>}

      {settlements.map((s) => {
        const iPay = s.from_user === myId;
        const iGet = s.to_user === myId;
        return (
          <View key={s.id} style={ui.card}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <Avatar id={iPay ? s.to_user : s.from_user} label={iPay ? "받" : "보"} size={40} />
              <View style={{ flex: 1 }}>
                <Text style={ui.cardTitle}>{iPay ? "내가 보낼 돈" : iGet ? "내가 받을 돈" : "다른 가정 간"}</Text>
                <Text style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>
                  {s.month} · {s.amount_credits === 0 ? "호스트 사례" : `크레딧 ${s.amount_credits}`}
                </Text>
              </View>
              <Text style={{ fontSize: 18, fontWeight: "700", color: t.ink }}>{s.amount_krw.toLocaleString()}원</Text>
            </View>
            {s.unsettled && iPay && (
              <Btn
                label="토스로 송금"
                tone="coral"
                onPress={() =>
                  Linking.openURL(`supertoss://send?amount=${s.amount_krw}`).catch(() =>
                    notify("안내", "토스 앱이 없어요. 페이 앱에서 직접 송금해주세요."),
                  )
                }
              />
            )}
            {s.unsettled && iGet && <Btn label="받았어요" onPress={guard(() => api.post(`/settlements/${s.id}/received`))} />}
            {!s.unsettled && <Text style={[ui.hint, { color: t.mintDeep, fontWeight: "700" }]}>완료됨 · 장부에서 상쇄됐어요</Text>}
          </View>
        );
      })}

      {unsettled.length > 0 && (
        <Btn
          label="미정산 독촉 보내기 — 악역은 앱이 할게요"
          tone="soft"
          onPress={guard(async () => {
            const r = await api.post<{ nudged_users: number }>(`/crews/${crewId}/settlements/nudge`);
            notify("독촉 완료", `${r.nudged_users}명에게 알림을 보냈어요. 매일 아침에도 자동으로 알려드려요.`);
          })}
        />
      )}
      <Text style={ui.hint}>
        앱은 계산·안내·독촉까지만 해요. 실제 송금은 각 가정이 페이 앱에서 직접 하고, 받은 쪽이 “받았어요”를 누르면
        장부에서 상쇄돼요.
      </Text>
    </View>
  );

  return (
    <Page wide>
      <PageHeader title="장부·정산" sub={`${route.params?.name ?? "크루"} · ${currentMonth()}`} />
      <Columns left={balanceCol} right={settleCol} ratio={1} />
    </Page>
  );
}
