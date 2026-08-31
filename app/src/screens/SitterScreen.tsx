import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, Child, SitterRequest } from "../api";
import { ui } from "../ui";

function nextMonday(): string {
  const d = new Date();
  d.setDate(d.getDate() + (((8 - d.getDay()) % 7) || 7));
  return d.toISOString().slice(0, 10);
}

/** 시터 공구 (P10, §25): 빈칸의 폴백 2단계. 금액은 계산·안내까지 — 결제 없음. */
export default function SitterScreen({ route }: any) {
  const { crewId } = route.params;
  const [requests, setRequests] = useState<SitterRequest[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [profile, setProfile] = useState<{ hourly_krw: number } | null>(null);
  const [hourly, setHourly] = useState("");
  const [date, setDate] = useState(nextMonday());
  const [hours, setHours] = useState("14-17");

  const load = useCallback(() => {
    api.get<SitterRequest[]>(`/crews/${crewId}/sitter-requests`).then(setRequests).catch(() => {});
    api.get<Child[]>("/my/children").then(setChildren).catch(() => {});
    api.get<{ hourly_krw: number } | null>("/sitters/me").then(setProfile).catch(() => {});
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

  const createRequest = guard(async () => {
    const m = /^(\d{1,2})-(\d{1,2})$/.exec(hours.trim());
    if (!m) throw new Error("시간은 14-17 형식으로 입력해주세요");
    if (children.length === 0) throw new Error("먼저 홈에서 아이를 등록해주세요");
    await api.post(`/crews/${crewId}/sitter-requests`, {
      date: date.trim(),
      start_hour: Number(m[1]),
      end_hour: Number(m[2]),
      child_ids: children.map((c) => c.id),
    });
  });

  const joinAll = (requestId: string) =>
    guard(async () => {
      for (const c of children) {
        await api.post(`/sitter-requests/${requestId}/join`, { child_id: c.id });
      }
    })();

  return (
    <ScrollView style={ui.screen}>
      <Text style={ui.sectionTitle}>공구 요청 만들기 (내 아이 전체로)</Text>
      <View style={ui.row}>
        <TextInput style={[ui.input, { flex: 1, marginRight: 8 }]} value={date} onChangeText={setDate} placeholder="2026-09-07" />
        <TextInput style={[ui.input, { width: 90 }]} value={hours} onChangeText={setHours} placeholder="14-17" />
      </View>
      <TouchableOpacity style={ui.primaryBtn} onPress={createRequest}>
        <Text style={ui.primaryBtnText}>시터 공구 요청</Text>
      </TouchableOpacity>
      <Text style={ui.hint}>당일 요청은 긴급 할증 1.5배가 붙어요. 지불은 각 가정이 직접 — 앱은 계산·안내만.</Text>

      <Text style={ui.sectionTitle}>공구 요청 ({requests.length})</Text>
      {requests.map((r) => (
        <View key={r.id} style={ui.card}>
          <Text style={{ fontWeight: "700" }}>
            {r.date} {r.start_hour}시~{r.end_hour}시 · 아이 {r.child_count} ·{" "}
            {r.status === "open" ? "견적 받는 중" : r.status === "matched" ? "매칭됨" : "종료"}
          </Text>
          {r.status === "open" && (
            <View style={ui.row}>
              <TouchableOpacity style={ui.smallBtn} onPress={() => joinAll(r.id)}>
                <Text style={ui.smallBtnText}>내 아이도 참여</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={ui.smallBtn}
                onPress={guard(() => api.post(`/sitter-requests/${r.id}/quotes`))}
              >
                <Text style={ui.smallBtnText}>견적 보내기 (시터)</Text>
              </TouchableOpacity>
            </View>
          )}
          {r.quotes.map((q) => (
            <View key={q.id} style={[ui.card, { marginTop: 8 }]}>
              <Text>
                총 {q.total_krw.toLocaleString()}원 · 가정당 {q.per_family_krw.toLocaleString()}원
                {q.surge ? " · 긴급 1.5배" : ""} ·{" "}
                {q.status === "proposed" ? "후보" : q.status === "confirmed" ? "확정" : "거절됨"}
              </Text>
              <Text style={ui.hint}>
                확정 {q.families.filter((f) => f.confirmed).length}/{q.families.length} 가정 — 전 가정 확정 시 세션 성립
              </Text>
              {q.status === "proposed" && r.status === "open" && (
                <View style={ui.row}>
                  <TouchableOpacity
                    style={ui.smallBtn}
                    onPress={guard(() => api.post(`/sitter-quotes/${q.id}/confirm`))}
                  >
                    <Text style={ui.smallBtnText}>내 가정 확정 탭</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={ui.smallBtn}
                    onPress={guard(() => api.post(`/sitter-quotes/${q.id}/decline`))}
                  >
                    <Text style={ui.smallBtnText}>거절</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          ))}
        </View>
      ))}

      <Text style={ui.sectionTitle}>시터로 활동하기</Text>
      <Text style={ui.hint}>
        {profile ? `내 시급: ${profile.hourly_krw.toLocaleString()}원` : "시급을 등록하면 견적을 보낼 수 있어요 (시터 초대로 합류한 크루에서)"}
      </Text>
      <View style={ui.row}>
        <TextInput
          style={[ui.input, { flex: 1, marginRight: 8 }]}
          placeholder="시급 (원)"
          keyboardType="number-pad"
          value={hourly}
          onChangeText={setHourly}
        />
        <TouchableOpacity
          style={ui.primaryBtn}
          onPress={guard(async () => {
            const v = Number(hourly);
            if (!v || v <= 0) throw new Error("시급을 입력해주세요");
            await api.post("/sitters/me", { hourly_krw: v });
            setHourly("");
          })}
        >
          <Text style={ui.primaryBtnText}>시급 저장</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}
