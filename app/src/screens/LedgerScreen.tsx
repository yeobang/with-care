import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Alert, Linking, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { api } from "../api";
import { ui } from "../ui";

interface Settlement {
  id: string;
  month: string;
  from_user: string;
  to_user: string;
  amount_krw: number;
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
    AsyncStorage.getItem("userId").then(setMyId);
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
      Alert.alert(e.invariant ? `가드레일 ${e.invariant}` : "오류", e.message);
    }
  };

  const unsettledCount = settlements.filter((s) => s.unsettled).length;

  return (
    <ScrollView style={ui.screen}>
      <Text style={ui.sectionTitle}>크레딧 잔액 (아이·시간)</Text>
      {Object.keys(balances).length === 0 && <Text style={ui.hint}>아직 기록이 없어요</Text>}
      {Object.entries(balances).map(([uid, bal]) => (
        <View key={uid} style={ui.card}>
          <Text style={{ fontWeight: uid === myId ? "700" : "400" }}>
            {uid === myId ? "나" : `이웃 (${uid.slice(0, 6)})`} · {bal > 0 ? `+${bal}` : bal}
          </Text>
        </View>
      ))}

      <Text style={ui.sectionTitle}>
        이번 달 정산 {unsettledCount > 0 ? `· 미정산 ${unsettledCount}건` : ""}
      </Text>
      <TouchableOpacity
        style={ui.primaryBtn}
        onPress={guard(() => api.post(`/crews/${crewId}/settlements/${currentMonth()}/compute`))}
      >
        <Text style={ui.primaryBtnText}>{currentMonth()} 정산 계산하기</Text>
      </TouchableOpacity>
      <Text style={ui.hint}>
        정산 모드가 &quot;credit&quot;인 크루만 계산됩니다. 앱은 계산·안내만 하고 돈은 만지지 않아요.
      </Text>

      {settlements.map((s) => (
        <View key={s.id} style={ui.card}>
          <Text style={{ fontWeight: "700" }}>
            {s.month} · {s.amount_krw.toLocaleString()}원 {s.unsettled ? "· 미정산" : "· 완료 ✓"}
          </Text>
          <Text style={ui.hint}>
            {s.from_user === myId ? "내가 보낼 돈" : s.to_user === myId ? "내가 받을 돈" : "다른 가정 간"}
          </Text>
          <View style={ui.row}>
            {s.unsettled && s.from_user === myId && (
              <TouchableOpacity
                style={ui.smallBtn}
                onPress={() => Linking.openURL(`supertoss://send?amount=${s.amount_krw}`).catch(() => Alert.alert("안내", "토스 앱이 없어요. 페이 앱에서 직접 송금해주세요."))}
              >
                <Text style={ui.smallBtnText}>토스로 송금</Text>
              </TouchableOpacity>
            )}
            {s.unsettled && s.to_user === myId && (
              <TouchableOpacity
                style={ui.smallBtn}
                onPress={guard(() => api.post(`/settlements/${s.id}/received`))}
              >
                <Text style={ui.smallBtnText}>받았어요 ✓</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}
