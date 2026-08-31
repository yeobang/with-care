import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Alert, Image, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { api, Assignment, CareSession, Child, Slot, uploadSessionPhoto } from "../api";
import { ui } from "../ui";

interface Photo {
  id: string;
  url: string;
}

const HOURS = [13, 14, 15, 16, 17, 18, 19];

function nextMonday(): string {
  const d = new Date();
  d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7));
  return d.toISOString().slice(0, 10);
}

export default function BoardScreen({ route }: any) {
  const { crewId } = route.params;
  const [date] = useState(nextMonday());
  const [myId, setMyId] = useState<string | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [proposals, setProposals] = useState<Assignment[]>([]);
  const [sessions, setSessions] = useState<CareSession[]>([]);
  const [photos, setPhotos] = useState<Record<string, Photo[]>>({});
  const [mode, setMode] = useState<"available" | "need">("available");

  useEffect(() => {
    // JWT·dev 헤더 어느 쪽이든 서버가 아는 내 id
    api.get<{ id: string }>("/me").then((u) => setMyId(u.id)).catch(() => {});
  }, []);

  const load = useCallback(() => {
    api.get<Slot[]>(`/crews/${crewId}/board?date=${date}`).then(setSlots).catch(() => {});
    api.get<Assignment[]>(`/crews/${crewId}/proposals?date=${date}`).then(setProposals).catch(() => {});
    api
      .get<CareSession[]>(`/crews/${crewId}/sessions`)
      .then(async (list) => {
        setSessions(list);
        const entries = await Promise.all(
          list.map(async (s) => [s.id, await api.get<Photo[]>(`/sessions/${s.id}/photos`).catch(() => [])] as const),
        );
        setPhotos(Object.fromEntries(entries));
      })
      .catch(() => {});
    api.get<Child[]>("/my/children").then(setChildren).catch(() => {});
  }, [crewId, date]);
  useFocusEffect(load);

  const guard = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      Alert.alert(e.invariant ? `가드레일 ${e.invariant}` : "오류", e.message);
    }
  };

  const tapHour = (hour: number) =>
    guard(async () => {
      if (mode === "need" && children.length === 0) {
        throw new Error("먼저 홈에서 아이를 등록해주세요");
      }
      await api.post(`/crews/${crewId}/slots`, {
        kind: mode,
        date,
        start_hour: hour,
        end_hour: hour + 1,
        child_id: mode === "need" ? children[0].id : null,
      });
    })();

  const pickPhoto = (sessionId: string) =>
    guard(async () => {
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: "images", quality: 0.7 });
      if (result.canceled) return;
      await uploadSessionPhoto(sessionId, result.assets[0].uri);
    })();

  const mySlots = slots.filter((s) => s.user_id === myId);
  const covered = (h: number, kind: string) =>
    mySlots.some((s) => s.kind === kind && s.start_hour <= h && h < s.end_hour);

  return (
    <ScrollView style={ui.screen}>
      <Text style={ui.sectionTitle}>{date} (다음 주 월요일)</Text>
      <View style={ui.row}>
        {(["available", "need"] as const).map((m) => (
          <TouchableOpacity
            key={m}
            style={[ui.smallBtn, mode === m && ui.smallBtnActive]}
            onPress={() => setMode(m)}
          >
            <Text style={[ui.smallBtnText, mode === m && ui.smallBtnTextActive]}>
              {m === "available" ? "돌봄 가능" : "돌봄 필요"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={ui.row}>
        {HOURS.map((h) => (
          <TouchableOpacity
            key={h}
            style={[ui.smallBtn, covered(h, mode) && ui.smallBtnActive]}
            onPress={() => tapHour(h)}
          >
            <Text style={[ui.smallBtnText, covered(h, mode) && ui.smallBtnTextActive]}>{h}시</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={ui.hint}>탭으로 시간을 등록하세요 · 크루 전체 슬롯 {slots.length}개</Text>

      <TouchableOpacity
        style={ui.primaryBtn}
        onPress={guard(() => api.post(`/crews/${crewId}/propose?date=${date}`))}
      >
        <Text style={ui.primaryBtnText}>배정 후보 만들기</Text>
      </TouchableOpacity>

      <Text style={ui.sectionTitle}>배정 후보 (전 가정 확정 시 세션 생성)</Text>
      {proposals.map((p) => (
        <View key={p.id} style={ui.card}>
          <Text style={{ fontWeight: "700" }}>
            {p.start_hour}시~{p.end_hour}시 · {p.status === "confirmed" ? "확정됨" : "후보"}
          </Text>
          {p.children.map((c) => (
            <Text key={c.child_id} style={{ fontSize: 13 }}>
              {c.child_name} {c.guardian_confirmed ? "✓ 확정" : "· 대기"}
            </Text>
          ))}
          {p.status === "proposed" && (
            <TouchableOpacity
              style={ui.smallBtn}
              onPress={guard(() => api.post(`/assignments/${p.id}/confirm`))}
            >
              <Text style={ui.smallBtnText}>내 아이 확정 탭</Text>
            </TouchableOpacity>
          )}
        </View>
      ))}

      <Text style={ui.sectionTitle}>세션</Text>
      {sessions.map((s) => (
        <View key={s.id} style={ui.card}>
          <Text style={{ fontWeight: "700" }}>
            {s.date} {s.start_hour}시~{s.end_hour}시
          </Text>
          <Text style={ui.hint}>
            인계 {s.handoff_started_at ? "시작됨" : "전"} · {s.handoff_ended_at ? "종료됨" : "진행 중"}
          </Text>
          <View style={ui.row}>
            {!s.handoff_started_at && (
              <TouchableOpacity
                style={ui.smallBtn}
                onPress={guard(() => api.post(`/sessions/${s.id}/handoff/start`))}
              >
                <Text style={ui.smallBtnText}>맡김 확인</Text>
              </TouchableOpacity>
            )}
            {s.handoff_started_at && !s.handoff_ended_at && (
              <TouchableOpacity
                style={ui.smallBtn}
                onPress={guard(() => api.post(`/sessions/${s.id}/handoff/end`))}
              >
                <Text style={ui.smallBtnText}>돌려받음 확인</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity style={ui.smallBtn} onPress={() => pickPhoto(s.id)}>
              <Text style={ui.smallBtnText}>📷 사진 올리기</Text>
            </TouchableOpacity>
          </View>
          <View style={ui.row}>
            {(photos[s.id] ?? []).map((p) => (
              <Image
                key={p.id}
                source={{ uri: p.url }}
                style={{ width: 72, height: 72, borderRadius: 8, marginRight: 6, marginTop: 6 }}
              />
            ))}
          </View>
        </View>
      ))}
    </ScrollView>
  );
}
