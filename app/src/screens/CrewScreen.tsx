import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Alert, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { api, CrewView } from "../api";
import { ui } from "../ui";

interface Charter {
  settlement_mode: string;
  credit_price_krw: number;
  host_fee_krw: number;
  no_show_fine_krw: number;
  is_complete: boolean;
}

export default function CrewScreen({ route, navigation }: any) {
  const { crewId } = route.params;
  const [crew, setCrew] = useState<CrewView | null>(null);
  const [charter, setCharter] = useState<Charter | null>(null);
  const [invite, setInvite] = useState<string | null>(null);

  const load = useCallback(() => {
    api.get<CrewView>(`/crews/${crewId}`).then(setCrew).catch(() => {});
    api.get<Charter>(`/crews/${crewId}/charter`).then(setCharter).catch(() => {});
  }, [crewId]);
  useFocusEffect(load);

  const act = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      Alert.alert(e.invariant ? `가드레일 ${e.invariant}` : "오류", e.message);
    }
  };

  if (!crew) return <View style={ui.screen} />;

  return (
    <ScrollView style={ui.screen}>
      <Text style={ui.title}>{crew.name}</Text>
      <Text style={ui.subtitle}>
        {crew.status === "active" ? "활성 크루" : "규약 합의 중"} · {crew.member_count}가구
      </Text>

      <Text style={ui.sectionTitle}>초대</Text>
      <TouchableOpacity
        style={ui.primaryBtn}
        onPress={act(async () => {
          const r = await api.post<{ token: string }>(`/crews/${crewId}/invites`);
          setInvite(r.token);
        })}
      >
        <Text style={ui.primaryBtnText}>초대 토큰 만들기</Text>
      </TouchableOpacity>
      {invite && (
        <View style={ui.card}>
          <Text selectable style={{ fontSize: 12 }}>{invite}</Text>
          <Text style={ui.hint}>카톡방에 이 토큰을 공유하세요 (P5에서 링크로 대체)</Text>
        </View>
      )}

      {crew.status !== "active" && (
        <>
          <Text style={ui.sectionTitle}>활성화 절차</Text>
          <TouchableOpacity
            style={ui.primaryBtn}
            onPress={act(() =>
              api.post(`/crews/${crewId}/consent`, {
                liability_ack: true,
                photo_consent: true,
                guardian_consent: true,
              }),
            )}
          >
            <Text style={ui.primaryBtnText}>포괄 합의 (책임·사진·법정대리인)</Text>
          </TouchableOpacity>
          {charter && (
            <View style={ui.card}>
              <Text style={{ fontWeight: "700" }}>규약 (기본값 제시)</Text>
              <Text>정산 모드: {charter.settlement_mode}</Text>
              <Text>1크레딧(1시간) = {charter.credit_price_krw.toLocaleString()}원</Text>
              <Text>호스트 사례 = {charter.host_fee_krw.toLocaleString()}원</Text>
              <Text>노쇼 벌금 = {charter.no_show_fine_krw.toLocaleString()}원</Text>
              <Text style={ui.hint}>{charter.is_complete ? "확정됨" : "미확정"}</Text>
            </View>
          )}
          <TouchableOpacity
            style={ui.primaryBtn}
            onPress={act(() => api.post(`/crews/${crewId}/charter/confirm`, {}))}
          >
            <Text style={ui.primaryBtnText}>규약 확정</Text>
          </TouchableOpacity>
          <TouchableOpacity style={ui.primaryBtn} onPress={act(() => api.post(`/crews/${crewId}/activate`))}>
            <Text style={ui.primaryBtnText}>크루 활성화</Text>
          </TouchableOpacity>
        </>
      )}

      {crew.status === "active" && (
        <TouchableOpacity
          style={ui.primaryBtn}
          onPress={() => navigation.navigate("Board", { crewId, name: crew.name })}
        >
          <Text style={ui.primaryBtnText}>주간 보드 열기</Text>
        </TouchableOpacity>
      )}
    </ScrollView>
  );
}
