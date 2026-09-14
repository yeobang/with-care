import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { Btn, Columns, Empty, NavBar, Note, Page, PageHeader, Pill } from "../components";
import { DatePicker, HourRangePicker, SkeletonCard } from "../pickers";
import { notify, notifyError } from "../notify";
import { api, Child, SitterRequest } from "../api";
import { t, ui } from "../ui";

function nextMonday(): string {
  const d = new Date();
  d.setDate(d.getDate() + (((8 - d.getDay()) % 7) || 7));
  return d.toISOString().slice(0, 10);
}

/** 시터 공구 (P10, §25): 빈칸의 폴백 2단계. 금액은 계산·안내까지 — 결제 없음. */
export default function SitterScreen({ route, navigation }: any) {
  const { crewId } = route.params;
  const [requests, setRequests] = useState<SitterRequest[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [profile, setProfile] = useState<{ hourly_krw: number } | null>(null);
  const [hourly, setHourly] = useState("");
  const [date, setDate] = useState(nextMonday());
  const [startH, setStartH] = useState<number | null>(14);
  const [endH, setEndH] = useState<number | null>(17);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    api.get<SitterRequest[]>(`/crews/${crewId}/sitter-requests`).then(setRequests).catch(() => {});
    api.get<Child[]>("/my/children").then(setChildren).catch(() => {});
    api.get<{ hourly_krw: number } | null>("/sitters/me").then(setProfile).catch(() => {}).finally(() => setLoading(false));
  }, [crewId]);
  useFocusEffect(load);

  const guard = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      notifyError(e);
    }
  };

  const createRequest = guard(async () => {
    if (startH === null || endH === null) throw new Error("돌봄이 필요한 시간을 골라주세요");
    if (children.length === 0) throw new Error("먼저 홈에서 아이를 등록해주세요");
    await api.post(`/crews/${crewId}/sitter-requests`, {
      date,
      start_hour: startH,
      end_hour: endH,
      child_ids: children.map((c) => c.id),
    });
    notify("요청을 올렸어요", "시터가 견적을 보내면 알려드릴게요", "success");
  });

  const joinAll = (requestId: string) =>
    guard(async () => {
      for (const c of children) {
        await api.post(`/sitter-requests/${requestId}/join`, { child_id: c.id });
      }
    })();

  return (
    <Page wide nav={<NavBar navigation={navigation} crewId={crewId} crewName={route.params?.name} active="sitter" />}>
      <PageHeader title="시터 함께 부르기" sub="여러 집이 나눠서 — 금액은 계산·안내까지" />
      <Text style={ui.sectionTitle}>함께 시터 부르기</Text>
      <Note icon="users">
        여러 집이 같은 시간대에 함께 부르면 비용을 나눠 낼 수 있어요. 우리 아이 전체로 요청이 올라갑니다.
      </Note>
      <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub, marginBottom: 6 }}>언제가 필요하세요?</Text>
      <DatePicker value={date} onChange={setDate} weekStart={nextMonday()} />
      <View style={{ height: 14 }} />
      <HourRangePicker start={startH} end={endH} onChange={(a, b) => { setStartH(a); setEndH(b); }} />
      <Btn label="시터 요청 올리기" onPress={createRequest} />
      <Text style={ui.hint}>당일 요청은 긴급 할증 1.5배가 붙어요. 지불은 각 가정이 직접 — 앱은 계산·안내만.</Text>

      <Text style={ui.sectionTitle}>올라온 요청 ({requests.length})</Text>
      {loading && <SkeletonCard lines={2} />}
      {!loading && requests.length === 0 && (
        <Empty icon="brief" title="아직 요청이 없어요" body="위에서 시간을 고르고 요청을 올리면 시터가 견적을 보내요." />
      )}
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
          placeholderTextColor={t.sub} placeholder="시급 (원)"
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
    </Page>
  );
}
