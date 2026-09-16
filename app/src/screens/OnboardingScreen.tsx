import AsyncStorage from "@react-native-async-storage/async-storage";
import { useState } from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";
import { Btn } from "../components";
import { Icon } from "../Icon";
import { t, ui, useLayout } from "../ui";

export const ONBOARDED_KEY = "onboarded.v1";

/* 실제 화면을 축소해 보여주는 미니 목업 — 말 대신 그림으로 설명한다 */

function MiniBoard() {
  const days = ["월", "화", "수", "목", "금"];
  const cells = [
    ["a", "", "n", "", "a"],
    ["s", "", "g", "n", "a"],
    ["s", "a", "g", "n", ""],
  ];
  const color = (k: string) =>
    k === "a" ? [t.mintTint, "#CFEBE2"] : k === "n" ? [t.coralTint, "#F8D9D1"] : k === "s" ? [t.mint, t.mint] : k === "g" ? [t.lemonTint, t.lemon] : [t.bg, t.border];
  return (
    <View style={[ui.card, { padding: 16, marginBottom: 0 }]}>
      <View style={{ flexDirection: "row", gap: 6, marginBottom: 8 }}>
        <View style={{ width: 26 }} />
        {days.map((d) => (
          <View key={d} style={{ flex: 1, alignItems: "center" }}>
            <Text style={{ fontSize: 11, color: t.sub }}>{d}</Text>
          </View>
        ))}
      </View>
      {cells.map((row, i) => (
        <View key={i} style={{ flexDirection: "row", gap: 6, marginBottom: 6, alignItems: "center" }}>
          <Text style={{ width: 26, fontSize: 10, color: t.sub, textAlign: "right" }}>{15 + i}시</Text>
          {row.map((k, j) => {
            const [bg, bd] = color(k);
            return (
              <View key={j} style={{ flex: 1, height: 26, borderRadius: 8, backgroundColor: bg, borderWidth: 1, borderColor: bd, alignItems: "center", justifyContent: "center" }}>
                {k === "s" && <Text style={{ fontSize: 9, color: "#fff", fontWeight: "700" }}>확정</Text>}
                {k === "g" && <Text style={{ fontSize: 9, color: t.lemonDeep, fontWeight: "700" }}>빈칸</Text>}
              </View>
            );
          })}
        </View>
      ))}
      <View style={{ flexDirection: "row", gap: 12, marginTop: 6, flexWrap: "wrap" }}>
        {[["봐줄 수 있음", t.mintTint, "#CFEBE2"], ["봐줘야 함", t.coralTint, "#F8D9D1"], ["정해짐", t.mint, t.mint]].map(([l, bg, bd]) => (
          <View key={l as string} style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
            <View style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: bg as string, borderWidth: 1, borderColor: bd as string }} />
            <Text style={{ fontSize: 10, color: t.sub }}>{l}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function MiniLedger() {
  const rows: [string, number, boolean][] = [["나", 3, true], ["지우네", 1, false], ["서준네", 2, false]];
  return (
    <View style={[ui.card, { padding: 16, marginBottom: 0 }]}>
      {rows.map(([name, v, pos]) => (
        <View key={name} style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <Text style={{ width: 54, fontSize: 12, fontWeight: name === "나" ? "700" : "400", color: t.ink }}>{name}</Text>
          <View style={{ flex: 1, height: 10, borderRadius: 999, backgroundColor: t.bg, flexDirection: "row", justifyContent: pos ? "flex-start" : "flex-end", overflow: "hidden" }}>
            <View style={{ width: `${v * 28}%`, backgroundColor: pos ? t.mint : t.coral, borderRadius: 999 }} />
          </View>
          <Text style={{ width: 30, textAlign: "right", fontSize: 12, fontWeight: "700", color: pos ? t.mintDeep : t.coralDeep }}>
            {pos ? `+${v}` : `−${v}`}
          </Text>
        </View>
      ))}
      <View style={{ backgroundColor: t.bg, borderRadius: 12, padding: 12, marginTop: 4 }}>
        <Text style={{ fontSize: 12, color: t.ink, fontWeight: "700" }}>지우네 → 나 · 8,000원</Text>
        <Text style={{ fontSize: 11, color: t.sub, marginTop: 3 }}>앱이 계산하고 대신 알려줘요</Text>
      </View>
    </View>
  );
}

function MiniNudge() {
  return (
    <View style={{ gap: 10 }}>
      {[
        ["📣", "이번 주 되는 시간 알려주세요", "일요일 저녁 6시"],
        ["🕒", "내일 15시 서연이 돌봄 있어요", "하루 전"],
        ["💸", "8,000원 아직 안 보내셨어요", "매일 아침 9시"],
      ].map(([icon, title, when]) => (
        <View key={title} style={{ flexDirection: "row", gap: 12, backgroundColor: t.card, borderWidth: 1, borderColor: t.border, borderRadius: 16, padding: 14, alignItems: "center" }}>
          <View style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: t.mintTint, alignItems: "center", justifyContent: "center" }}>
            <Text style={{ fontSize: 16 }}>{icon}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13, fontWeight: "700", color: t.ink }}>{title}</Text>
            <Text style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>{when}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const SLIDES = [
  {
    tag: "이런 적 있으시죠",
    title: "“오늘 우리 애 좀\n봐줄 수 있어?”",
    body: "그 말 꺼내기가 제일 어렵죠. 지난번에 누가 더 봐줬는지 세는 것도, 돈 얘기를 먼저 꺼내는 것도요.",
    visual: null,
  },
  {
    tag: "1. 시간만 눌러요",
    title: "되는 시간을 누르면\n앱이 짝을 맞춰요",
    body: "누가 언제 되는지 한 판에 보이고, 겹치는 시간을 앱이 찾아 후보로 올려요. 고르는 건 각 집이 직접 합니다.",
    visual: <MiniBoard />,
  },
  {
    tag: "2. 앱이 세어둬요",
    title: "누가 얼마나 봤는지\n자동으로 쌓여요",
    body: "말 안 해도 기록이 남아요. 월말에 얼마 주고받을지도 계산해드려요. 돈은 각자 직접 보내고요.",
    visual: <MiniLedger />,
  },
  {
    tag: "3. 조르는 건 앱이",
    title: "재촉하는 악역은\n앱이 맡을게요",
    body: "시간 입력도, 돌봄 알림도, 아직 안 보낸 정산도 앱이 대신 말해줘요. 서로 얼굴 붉힐 일이 없어요.",
    visual: <MiniNudge />,
  },
];

export default function OnboardingScreen({ navigation }: any) {
  const [i, setI] = useState(0);
  const { isWide } = useLayout();
  const slide = SLIDES[i];
  const last = i === SLIDES.length - 1;

  const finish = async () => {
    await AsyncStorage.setItem(ONBOARDED_KEY, "1");
    navigation.replace("Home");
  };

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <View style={{ position: "absolute", top: -140, right: -120, width: 320, height: 320, borderRadius: 999, backgroundColor: t.mintTint }} />
      <View style={{ position: "absolute", bottom: -130, left: -100, width: 260, height: 260, borderRadius: 999, backgroundColor: t.lemonTint }} />

      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: 24 }}>
        <View style={{ width: "100%", maxWidth: 480, alignSelf: "center", gap: 18 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <View style={{ flexDirection: "row", gap: 6 }}>
              {SLIDES.map((_, n) => (
                <View key={n} style={{ width: n === i ? 22 : 8, height: 8, borderRadius: 999, backgroundColor: n === i ? t.mint : t.border }} />
              ))}
            </View>
            <TouchableOpacity onPress={finish} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Text style={{ fontSize: 13, color: t.sub }}>건너뛰기</Text>
            </TouchableOpacity>
          </View>

          <Text style={{ fontSize: 13, fontWeight: "700", color: t.mintDeep }}>{slide.tag}</Text>
          <Text style={[ui.display, { fontSize: isWide ? 34 : 28, lineHeight: isWide ? 46 : 38 }]}>{slide.title}</Text>
          <Text style={{ fontSize: 15, color: t.sub, lineHeight: 24 }}>{slide.body}</Text>

          {slide.visual}

          <View style={{ flexDirection: "row", gap: 10, marginTop: 4 }}>
            {i > 0 && <Btn label="이전" tone="ghost" style={{ width: 92, marginTop: 0 }} onPress={() => setI(i - 1)} />}
            <Btn
              label={last ? "시작하기" : "다음"}
              style={{ flex: 1, marginTop: 0 }}
              onPress={() => (last ? finish() : setI(i + 1))}
            />
          </View>
        </View>
      </ScrollView>
    </View>
  );
}
