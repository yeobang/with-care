import { useEffect, useRef, useState } from "react";
import { Animated, Modal, Pressable, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { Icon } from "./Icon";
import { t, ui } from "./ui";

/* ─────────── 로딩 스켈레톤 ─────────── */

export function Skeleton({ h = 16, w = "100%", r = 8, mb = 8 }: { h?: number; w?: any; r?: number; mb?: number }) {
  const pulse = useRef(new Animated.Value(0.4)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.4, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  return <Animated.View style={{ height: h, width: w, borderRadius: r, marginBottom: mb, backgroundColor: t.border, opacity: pulse }} />;
}

export function SkeletonCard({ lines = 2 }: { lines?: number }) {
  return (
    <View style={[ui.card, { shadowOpacity: 0 }]}>
      <Skeleton h={18} w="55%" mb={12} />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} h={12} w={i === lines - 1 ? "40%" : "80%"} />
      ))}
    </View>
  );
}

/* ─────────── 공용 모달 껍데기 ─────────── */

function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: any }) {
  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={{ flex: 1, backgroundColor: "rgba(31,58,52,0.35)", justifyContent: "center", padding: 20 }} onPress={onClose}>
        <Pressable
          style={{ backgroundColor: t.card, borderRadius: 24, padding: 20, width: "100%", maxWidth: 420, alignSelf: "center" }}
          onPress={(e) => e.stopPropagation()}
        >
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <Text style={{ fontSize: 17, fontWeight: "700", color: t.ink }}>{title}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Text style={{ fontSize: 18, color: t.sub }}>✕</Text>
            </TouchableOpacity>
          </View>
          {children}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

/* ─────────── 생년월 선택기 ─────────── */

const MONTHS = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"];

export function MonthPicker({ value, onChange, placeholder = "태어난 달 선택" }: {
  value: string; // "YYYY-MM"
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const thisYear = new Date().getFullYear();
  const years = Array.from({ length: 15 }, (_, i) => thisYear - i);
  const [year, setYear] = useState(value ? Number(value.slice(0, 4)) : thisYear - 3);

  const label = value ? `${value.slice(0, 4)}년 ${Number(value.slice(5, 7))}월` : placeholder;

  return (
    <>
      <TouchableOpacity
        style={[ui.input, { flexDirection: "row", alignItems: "center", justifyContent: "space-between" }]}
        onPress={() => setOpen(true)}
      >
        <Text style={{ fontSize: 15, color: value ? t.ink : t.sub }}>{label}</Text>
        <Icon name="calendar" size={18} color={t.sub} />
      </TouchableOpacity>

      <Sheet open={open} onClose={() => setOpen(false)} title="태어난 해와 달">
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 14 }}>
          <View style={{ flexDirection: "row", gap: 8 }}>
            {years.map((y) => (
              <TouchableOpacity
                key={y}
                style={{
                  paddingVertical: 10,
                  paddingHorizontal: 16,
                  borderRadius: 13,
                  backgroundColor: y === year ? t.mint : t.bg,
                  borderWidth: 1,
                  borderColor: y === year ? t.mint : t.border,
                }}
                onPress={() => setYear(y)}
              >
                <Text style={{ fontSize: 14, fontWeight: "700", color: y === year ? "#fff" : t.ink }}>{y}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {MONTHS.map((m, i) => {
            const v = `${year}-${String(i + 1).padStart(2, "0")}`;
            const sel = v === value;
            return (
              <TouchableOpacity
                key={m}
                style={{
                  width: "22%",
                  minHeight: 46,
                  borderRadius: 13,
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: sel ? t.mintTint : t.bg,
                  borderWidth: 1,
                  borderColor: sel ? t.mint : t.border,
                }}
                onPress={() => {
                  onChange(v);
                  setOpen(false);
                }}
              >
                <Text style={{ fontSize: 14, fontWeight: sel ? "700" : "400", color: sel ? t.mintDeep : t.ink }}>{m}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </Sheet>
    </>
  );
}

/* ─────────── 날짜(일) 선택기 ─────────── */

export function DatePicker({ value, onChange, weekStart }: { value: string; onChange: (v: string) => void; weekStart?: string }) {
  const [open, setOpen] = useState(false);
  const base = weekStart ? new Date(weekStart + "T00:00:00") : new Date();
  const days = Array.from({ length: 21 }, (_, i) => {
    const d = new Date(base);
    d.setDate(d.getDate() + i);
    return d;
  });
  const DOW = ["일", "월", "화", "수", "목", "금", "토"];

  return (
    <>
      <TouchableOpacity
        style={[ui.input, { flexDirection: "row", alignItems: "center", justifyContent: "space-between" }]}
        onPress={() => setOpen(true)}
      >
        <Text style={{ fontSize: 15, color: t.ink }}>{value || "날짜 선택"}</Text>
        <Icon name="calendar" size={18} color={t.sub} />
      </TouchableOpacity>
      <Sheet open={open} onClose={() => setOpen(false)} title="날짜 고르기">
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {days.map((d) => {
            const iso = d.toISOString().slice(0, 10);
            const sel = iso === value;
            return (
              <TouchableOpacity
                key={iso}
                style={{
                  width: "22%",
                  paddingVertical: 10,
                  borderRadius: 13,
                  alignItems: "center",
                  backgroundColor: sel ? t.mint : t.bg,
                  borderWidth: 1,
                  borderColor: sel ? t.mint : t.border,
                }}
                onPress={() => {
                  onChange(iso);
                  setOpen(false);
                }}
              >
                <Text style={{ fontSize: 11, color: sel ? "rgba(255,255,255,0.85)" : t.sub }}>{DOW[d.getDay()]}</Text>
                <Text style={{ fontSize: 15, fontWeight: "700", color: sel ? "#fff" : t.ink }}>{d.getDate()}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </Sheet>
    </>
  );
}

/* ─────────── 시간 범위 선택기 ─────────── */

export function HourRangePicker({ start, end, onChange, from = 7, to = 22 }: {
  start: number | null;
  end: number | null;
  onChange: (s: number | null, e: number | null) => void;
  from?: number;
  to?: number;
}) {
  const hours = Array.from({ length: to - from + 1 }, (_, i) => from + i);

  const tap = (h: number) => {
    if (start === null || (start !== null && end !== null)) return onChange(h, null); // 새로 시작
    if (h <= start) return onChange(h, null); // 더 이른 시간을 누르면 시작점 이동
    onChange(start, h);
  };

  return (
    <View>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
        {hours.map((h) => {
          const isStart = h === start;
          const isEnd = h === end;
          const inRange = start !== null && end !== null && h > start && h < end;
          const active = isStart || isEnd;
          return (
            <TouchableOpacity
              key={h}
              style={{
                minWidth: 56,
                minHeight: 44,
                paddingHorizontal: 10,
                borderRadius: 13,
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: active ? t.mint : inRange ? t.mintTint : t.card,
                borderWidth: 1,
                borderColor: active ? t.mint : inRange ? "#CFEBE2" : t.border,
              }}
              onPress={() => tap(h)}
            >
              <Text style={{ fontSize: 14, fontWeight: active ? "700" : "400", color: active ? "#fff" : inRange ? t.mintDeep : t.ink }}>
                {h}시
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <Text style={{ fontSize: 12, color: t.sub, marginTop: 10, lineHeight: 18 }}>
        {start === null
          ? "시작 시간을 눌러주세요"
          : end === null
            ? `${start}시부터 — 끝나는 시간을 눌러주세요`
            : `${start}시 ~ ${end}시 (${end - start}시간)`}
      </Text>
    </View>
  );
}
