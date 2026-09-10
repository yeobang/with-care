import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Image, Text, TouchableOpacity, View } from "react-native";
import { api, Assignment, CareSession, Child, Slot, uploadSessionPhoto } from "../api";
import { Avatar, Btn, Columns, Page, PageHeader, Pill } from "../components";
import { notify } from "../notify";
import { t, ui, useLayout } from "../ui";

interface Photo {
  id: string;
  url: string;
}

interface Gap {
  guardian_id: string;
  child_id: string;
  start_hour: number;
  end_hour: number;
}

const HOURS = [13, 14, 15, 16, 17, 18, 19];
const DAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"];

function nextMonday(): string {
  const d = new Date();
  d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7));
  return d.toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

export default function BoardScreen({ route, navigation }: any) {
  const { crewId } = route.params;
  const [weekStart] = useState(nextMonday());
  const [date, setDate] = useState(weekStart);
  const [myId, setMyId] = useState<string | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [weekSlots, setWeekSlots] = useState<Record<string, Slot[]>>({});
  const [children, setChildren] = useState<Child[]>([]);
  const [proposals, setProposals] = useState<Assignment[]>([]);
  const [sessions, setSessions] = useState<CareSession[]>([]);
  const [photos, setPhotos] = useState<Record<string, Photo[]>>({});
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [mode, setMode] = useState<"available" | "need">("available");
  const { isWide } = useLayout();

  useEffect(() => {
    api.get<{ id: string }>("/me").then((u) => setMyId(u.id)).catch(() => {});
  }, []);

  const load = useCallback(() => {
    api.get<Slot[]>(`/crews/${crewId}/board?date=${date}`).then(setSlots).catch(() => {});
    api.get<Assignment[]>(`/crews/${crewId}/proposals?date=${date}`).then(setProposals).catch(() => {});
    api.get<Gap[]>(`/crews/${crewId}/board/gaps?date=${date}`).then(setGaps).catch(() => {});
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
    // 데스크톱 주간 그리드: 7일치를 병렬로 (크루 단위라 호출 수가 작다)
    Promise.all(
      DAY_LABELS.map((_, i) => {
        const d = addDays(weekStart, i);
        return api.get<Slot[]>(`/crews/${crewId}/board?date=${d}`).then((s) => [d, s] as const).catch(() => [d, []] as const);
      }),
    ).then((rows) => setWeekSlots(Object.fromEntries(rows)));
  }, [crewId, date, weekStart]);
  useFocusEffect(load);

  const guard = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      notify(e.invariant ? `가드레일 ${e.invariant}` : "오류", e.message);
    }
  };

  const tapHour = (hour: number, onDate = date) =>
    guard(async () => {
      if (mode === "need" && children.length === 0) throw new Error("먼저 홈에서 아이를 등록해주세요");
      await api.post(`/crews/${crewId}/slots`, {
        kind: mode,
        date: onDate,
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
  const covered = (h: number, kind: string) => mySlots.some((s) => s.kind === kind && s.start_hour <= h && h < s.end_hour);

  const modeToggle = (
    <View style={{ flexDirection: "row", backgroundColor: t.card, borderWidth: 1, borderColor: t.border, borderRadius: 16, padding: 4 }}>
      {(["available", "need"] as const).map((m) => (
        <TouchableOpacity
          key={m}
          style={{
            flex: 1,
            height: 44,
            borderRadius: 13,
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: mode === m ? t.mintTint : "transparent",
          }}
          onPress={() => setMode(m)}
        >
          <Text style={{ fontSize: 14, fontWeight: mode === m ? "700" : "400", color: mode === m ? t.mintDeep : t.sub }}>
            {m === "available" ? "돌봄 가능" : "돌봄 필요"}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  /** 데스크톱: 7일 × 시간 그리드 — 한 주가 한눈에 */
  const weekGrid = (
    <View style={[ui.card, { padding: 16 }]}>
      <View style={{ flexDirection: "row", gap: 6, marginBottom: 8 }}>
        <View style={{ width: 44 }} />
        {DAY_LABELS.map((d, i) => {
          const dIso = addDays(weekStart, i);
          const sel = dIso === date;
          return (
            <TouchableOpacity
              key={d}
              style={{
                flex: 1,
                alignItems: "center",
                paddingVertical: 8,
                borderRadius: 12,
                backgroundColor: sel ? t.mint : "transparent",
              }}
              onPress={() => setDate(dIso)}
            >
              <Text style={{ fontSize: 11, color: sel ? "rgba(255,255,255,0.85)" : t.sub }}>{d}</Text>
              <Text style={{ fontSize: 15, fontWeight: "700", color: sel ? "#fff" : t.ink }}>{dIso.slice(8)}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      {HOURS.map((h) => (
        <View key={h} style={{ flexDirection: "row", gap: 6, marginBottom: 6, alignItems: "center" }}>
          <Text style={{ width: 44, fontSize: 12, color: t.sub, textAlign: "right" }}>{h}시</Text>
          {DAY_LABELS.map((_, i) => {
            const dIso = addDays(weekStart, i);
            const daySlots = weekSlots[dIso] ?? [];
            const hasAvail = daySlots.some((s) => s.kind === "available" && s.start_hour <= h && h < s.end_hour);
            const hasNeed = daySlots.some((s) => s.kind === "need" && s.start_hour <= h && h < s.end_hour);
            const bg = hasAvail && hasNeed ? t.lemonTint : hasAvail ? t.mintTint : hasNeed ? t.coralTint : t.bg;
            const bd = hasAvail && hasNeed ? "#F3E4BE" : hasAvail ? "#CFEBE2" : hasNeed ? "#F8D9D1" : t.border;
            return (
              <TouchableOpacity
                key={i}
                style={{ flex: 1, height: 38, borderRadius: 10, backgroundColor: bg, borderWidth: 1, borderColor: bd }}
                onPress={() => tapHour(h, dIso)}
              />
            );
          })}
        </View>
      ))}
      <View style={{ flexDirection: "row", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
        {[
          ["돌봄 가능", t.mintTint, "#CFEBE2"],
          ["돌봄 필요", t.coralTint, "#F8D9D1"],
          ["둘 다", t.lemonTint, "#F3E4BE"],
        ].map(([label, bg, bd]) => (
          <View key={label} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <View style={{ width: 12, height: 12, borderRadius: 4, backgroundColor: bg, borderWidth: 1, borderColor: bd }} />
            <Text style={{ fontSize: 11, color: t.sub }}>{label}</Text>
          </View>
        ))}
      </View>
      <Text style={ui.hint}>칸을 눌러 “{mode === "available" ? "돌봄 가능" : "돌봄 필요"}”을 등록해요</Text>
    </View>
  );

  /** 모바일: 하루 선택 + 시간 칩 */
  const dayStrip = (
    <View>
      <View style={{ flexDirection: "row", gap: 6 }}>
        {DAY_LABELS.map((d, i) => {
          const dIso = addDays(weekStart, i);
          const sel = dIso === date;
          return (
            <TouchableOpacity
              key={d}
              style={{
                flex: 1,
                alignItems: "center",
                paddingVertical: 10,
                borderRadius: 14,
                backgroundColor: sel ? t.mint : t.card,
                borderWidth: sel ? 0 : 1,
                borderColor: t.border,
              }}
              onPress={() => setDate(dIso)}
            >
              <Text style={{ fontSize: 11, color: sel ? "rgba(255,255,255,0.85)" : t.sub }}>{d}</Text>
              <Text style={{ fontSize: 15, fontWeight: "700", color: sel ? "#fff" : t.ink }}>{dIso.slice(8)}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <View style={{ marginTop: 12 }}>{modeToggle}</View>
      <View style={ui.row}>
        {HOURS.map((h) => {
          const on = covered(h, mode);
          return (
            <TouchableOpacity key={h} style={[ui.smallBtn, on && ui.smallBtnActive, { minWidth: 66 }]} onPress={() => tapHour(h)}>
              <Text style={[ui.smallBtnText, on && ui.smallBtnTextActive]}>{h}시</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <Text style={ui.hint}>탭해서 시간을 등록하세요 · 크루 전체 슬롯 {slots.length}개</Text>
    </View>
  );

  const leftCol = (
    <View>
      {isWide ? (
        <View>
          <View style={{ marginBottom: 12 }}>{modeToggle}</View>
          {weekGrid}
        </View>
      ) : (
        dayStrip
      )}
      <Btn label="배정 후보 만들기" onPress={guard(() => api.post(`/crews/${crewId}/propose?date=${date}`))} />
    </View>
  );

  const rightCol = (
    <View>
      {gaps.length > 0 && (
        <View style={[ui.card, { backgroundColor: t.lemonTint, borderColor: "#F3E4BE", shadowOpacity: 0 }]}>
          <Text style={{ fontSize: 14, fontWeight: "700", color: t.lemonDeep }}>빈칸 {gaps.length}건</Text>
          {gaps.map((g, i) => (
            <Text key={i} style={{ fontSize: 12, color: t.lemonDeep, opacity: 0.85, marginTop: 4 }}>
              {g.start_hour}시~{g.end_hour}시 · 돌봐줄 이웃이 없어요
            </Text>
          ))}
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Btn
              label="크루에 재요청"
              tone="ghost"
              style={{ flex: 1 }}
              onPress={guard(() => api.post(`/crews/${crewId}/board/rerequest?date=${date}`))}
            />
            <Btn
              label="시터 공구"
              tone="ghost"
              style={{ flex: 1 }}
              onPress={() => navigation.navigate("Sitter", { crewId, name: route.params?.name })}
            />
          </View>
        </View>
      )}

      <Text style={ui.sectionTitle}>배정 후보</Text>
      {proposals.length === 0 && <Text style={ui.hint}>아직 후보가 없어요 — 시간을 등록하고 후보를 만들어보세요</Text>}
      {proposals.map((p) => (
        <View key={p.id} style={ui.card}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={ui.cardTitle}>
              {p.start_hour}시~{p.end_hour}시
            </Text>
            <Pill
              label={p.status === "confirmed" ? "확정됨" : p.status === "declined" ? "거절됨" : "후보"}
              tone={p.status === "confirmed" ? "mint" : p.status === "declined" ? "coral" : "neutral"}
            />
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10 }}>
            <Avatar id={p.caregiver_id} label="돌" size={30} />
            <Text style={{ fontSize: 13, color: t.ink }}>이 이웃이 돌봐요</Text>
          </View>
          <View style={{ marginTop: 10, gap: 8 }}>
            {p.children.map((c) => (
              <View
                key={c.child_id}
                style={{
                  flexDirection: "row",
                  justifyContent: "space-between",
                  alignItems: "center",
                  backgroundColor: c.guardian_confirmed ? t.mintTint : t.bg,
                  borderRadius: 12,
                  paddingVertical: 10,
                  paddingHorizontal: 14,
                }}
              >
                <Text style={{ fontSize: 14, color: t.ink }}>{c.child_name}</Text>
                <Text style={{ fontSize: 12, fontWeight: "700", color: c.guardian_confirmed ? t.mintDeep : t.sub }}>
                  {c.guardian_confirmed ? "확정" : "대기 중"}
                </Text>
              </View>
            ))}
          </View>
          {p.status === "proposed" && (
            <View style={{ flexDirection: "row", gap: 8 }}>
              <Btn label="내 아이 확정" style={{ flex: 1 }} onPress={guard(() => api.post(`/assignments/${p.id}/confirm`))} />
              <Btn label="거절" tone="ghost" style={{ width: 92 }} onPress={guard(() => api.post(`/assignments/${p.id}/decline`))} />
            </View>
          )}
        </View>
      ))}

      <Text style={ui.sectionTitle}>세션</Text>
      {sessions.length === 0 && <Text style={ui.hint}>아직 확정된 세션이 없어요</Text>}
      {sessions.map((s) => (
        <View key={s.id} style={ui.card}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={ui.cardTitle}>
              {s.date} {s.start_hour}시~{s.end_hour}시
            </Text>
            <Pill
              label={s.canceled_at ? "취소됨" : s.handoff_ended_at ? "종료" : s.handoff_started_at ? "진행 중" : "인계 전"}
              tone={s.canceled_at ? "coral" : s.handoff_started_at ? "mint" : "neutral"}
            />
          </View>
          <View style={[ui.row, { marginTop: 4 }]}>
            {(photos[s.id] ?? []).map((p) => (
              <Image key={p.id} source={{ uri: p.url }} style={{ width: 74, height: 74, borderRadius: 16, marginRight: 8, marginTop: 8 }} />
            ))}
            {!s.canceled_at && (
              <TouchableOpacity
                style={{
                  width: 74,
                  height: 74,
                  borderRadius: 16,
                  borderWidth: 2,
                  borderColor: t.border,
                  borderStyle: "dashed",
                  alignItems: "center",
                  justifyContent: "center",
                  marginTop: 8,
                }}
                onPress={() => pickPhoto(s.id)}
              >
                <Text style={{ fontSize: 12, color: t.sub }}>사진</Text>
              </TouchableOpacity>
            )}
          </View>
          {!s.canceled_at && (
            <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
              {!s.handoff_started_at && (
                <>
                  <Btn label="맡김 확인" style={{ flex: 1 }} onPress={guard(() => api.post(`/sessions/${s.id}/handoff/start`))} />
                  <Btn label="세션 취소" tone="ghost" style={{ width: 110 }} onPress={guard(() => api.post(`/sessions/${s.id}/cancel`))} />
                </>
              )}
              {s.handoff_started_at && !s.handoff_ended_at && (
                <Btn label="돌려받음 확인" style={{ flex: 1 }} onPress={guard(() => api.post(`/sessions/${s.id}/handoff/end`))} />
              )}
              {myId && myId !== s.caregiver_id && (
                <Btn
                  label="돌봄자 노쇼 기록"
                  tone="ghost"
                  onPress={guard(async () => {
                    await api.post(`/sessions/${s.id}/incidents`, { kind: "no_show", offender_id: s.caregiver_id });
                    notify("기록 완료", "규약의 벌금 안내를 앱이 대신 전했어요.");
                  })}
                />
              )}
            </View>
          )}
        </View>
      ))}
      <Text style={ui.hint}>사진은 크루 안에서만 보여요 · 외부 공유 기능은 없어요</Text>
    </View>
  );

  return (
    <Page wide>
      <PageHeader title="주간 보드" sub={`${weekStart} 주 · 선택: ${date}`} />
      <Columns left={leftCol} right={rightCol} ratio={1.6} />
    </Page>
  );
}
