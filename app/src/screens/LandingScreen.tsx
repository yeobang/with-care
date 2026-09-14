import { ScrollView, Text, View } from "react-native";
import { Btn } from "../components";
import { Icon, IconName } from "../Icon";
import { t, ui, useLayout } from "../ui";

/** 웹 현관의 첫 화면 — 링크를 받은 사람이 30초 안에 "이게 뭔지" 알게 한다. */
export default function LandingScreen({ navigation }: any) {
  const { isWide } = useLayout();
  const go = () => navigation.navigate("Login");

  const steps: { icon: IconName; title: string; body: string }[] = [
    {
      icon: "users",
      title: "친한 가족 3~6집이 모여요",
      body: "이미 아는 사이끼리만. 초대 링크를 받은 사람만 들어올 수 있어요.",
    },
    {
      icon: "calendar",
      title: "이번 주 되는 시간을 눌러요",
      body: "누가 언제 봐줄 수 있는지 앱이 맞춰서 후보를 보여줘요. 고르는 건 각 집이 직접.",
    },
    {
      icon: "coins",
      title: "누가 얼마나 봤는지 앱이 세요",
      body: "“지난번에 내가 더 봤는데” 같은 말을 꺼낼 필요가 없어요. 계산도 독촉도 앱이 해요.",
    },
  ];

  const worries: { icon: IconName; title: string; body: string }[] = [
    {
      icon: "shield",
      title: "아무나 못 들어와요",
      body: "본인인증과 초대를 둘 다 거쳐야 아이를 맡기고 맡을 수 있어요.",
    },
    {
      icon: "camera",
      title: "사진은 우리끼리만",
      body: "돌봄 중 사진은 그 모임 안에서만 보여요. 밖으로 내보내는 기능 자체가 없어요.",
    },
    {
      icon: "clock",
      title: "규칙을 먼저 정하고 시작해요",
      body: "간식·스크린타임·늦을 때 어떻게 할지. 앱이 기본안을 내면 고르기만 하면 돼요.",
    },
  ];

  return (
    <ScrollView style={{ flex: 1, backgroundColor: t.bg }} contentContainerStyle={{ paddingBottom: 60 }}>
      {/* Hero */}
      <View style={{ position: "relative", overflow: "hidden", paddingTop: isWide ? 70 : 46, paddingBottom: isWide ? 60 : 44 }}>
        <View style={{ position: "absolute", top: -150, right: -120, width: 360, height: 360, borderRadius: 999, backgroundColor: t.mintTint }} />
        <View style={{ position: "absolute", top: 120, left: -110, width: 240, height: 240, borderRadius: 999, backgroundColor: t.lemonTint }} />

        <View style={{ width: "100%", maxWidth: 940, alignSelf: "center", paddingHorizontal: 24, gap: 22 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <View style={{ width: 38, height: 38, borderRadius: 13, backgroundColor: t.mint, alignItems: "center", justifyContent: "center" }}>
              <Icon name="heart" size={19} color="#fff" width={2.2} />
            </View>
            <Text style={[ui.display, { fontSize: 22 }]}>with-care</Text>
          </View>

          <Text style={[ui.display, { fontSize: isWide ? 52 : 34, lineHeight: isWide ? 64 : 44 }]}>
            “오늘 우리 애 좀{"\n"}봐줄 수 있어?”
          </Text>
          <Text style={{ fontSize: isWide ? 19 : 16, color: t.sub, lineHeight: isWide ? 30 : 26, maxWidth: 560 }}>
            그 말을 꺼내기가 제일 어렵죠. 누가 더 봐줬는지 세는 것도, 돈 얘기를 먼저 꺼내는 것도요.
            <Text style={{ color: t.ink, fontWeight: "700" }}> 그 불편한 몫을 앱이 대신합니다.</Text>
          </Text>

          <View style={{ flexDirection: isWide ? "row" : "column", gap: 12, marginTop: 6, maxWidth: 460 }}>
            <Btn label="시작하기" onPress={go} style={{ flex: isWide ? 1 : undefined, marginTop: 0 }} />
            <Btn label="이미 초대를 받았어요" tone="ghost" onPress={go} style={{ flex: isWide ? 1 : undefined, marginTop: 0 }} />
          </View>
          <Text style={{ fontSize: 12, color: t.sub }}>가입은 이메일로 1분이면 끝나요</Text>
        </View>
      </View>

      {/* 어떻게 쓰나 */}
      <View style={{ width: "100%", maxWidth: 940, alignSelf: "center", paddingHorizontal: 24, marginTop: 10 }}>
        <Text style={[ui.display, { fontSize: isWide ? 30 : 24, marginBottom: 18 }]}>이렇게 씁니다</Text>
        <View style={{ flexDirection: isWide ? "row" : "column", gap: 14 }}>
          {steps.map((s, i) => (
            <View key={s.title} style={[ui.card, { flex: 1, marginBottom: 0, padding: 22 }]}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <View style={{ width: 40, height: 40, borderRadius: 14, backgroundColor: t.mintTint, alignItems: "center", justifyContent: "center" }}>
                  <Icon name={s.icon} size={20} color={t.mintDeep} />
                </View>
                <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub }}>{i + 1}단계</Text>
              </View>
              <Text style={{ fontSize: 17, fontWeight: "700", color: t.ink, marginBottom: 8 }}>{s.title}</Text>
              <Text style={{ fontSize: 14, color: t.sub, lineHeight: 22 }}>{s.body}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* 걱정되는 것 */}
      <View style={{ width: "100%", maxWidth: 940, alignSelf: "center", paddingHorizontal: 24, marginTop: 42 }}>
        <Text style={[ui.display, { fontSize: isWide ? 30 : 24, marginBottom: 8 }]}>맡기기 전에 걱정되는 것들</Text>
        <Text style={{ fontSize: 14, color: t.sub, marginBottom: 18 }}>먼저 정해두면 서로 얼굴 붉힐 일이 없어요.</Text>
        <View style={{ flexDirection: isWide ? "row" : "column", gap: 14 }}>
          {worries.map((w) => (
            <View key={w.title} style={[ui.card, { flex: 1, marginBottom: 0, padding: 22, backgroundColor: t.card }]}>
              <Icon name={w.icon} size={22} color={t.coralDeep} />
              <Text style={{ fontSize: 16, fontWeight: "700", color: t.ink, marginTop: 12, marginBottom: 6 }}>{w.title}</Text>
              <Text style={{ fontSize: 14, color: t.sub, lineHeight: 22 }}>{w.body}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* 돈에 대한 약속 */}
      <View style={{ width: "100%", maxWidth: 940, alignSelf: "center", paddingHorizontal: 24, marginTop: 42 }}>
        <View style={[ui.card, { backgroundColor: t.deep, borderColor: t.deep, padding: isWide ? 34 : 24, marginBottom: 0 }]}>
          <Text style={[ui.display, { fontSize: isWide ? 26 : 21, color: "#fff", marginBottom: 12 }]}>
            앱은 돈을 만지지 않습니다
          </Text>
          <Text style={{ fontSize: 15, color: t.deepSub, lineHeight: 25, maxWidth: 620 }}>
            서로 도운 만큼을 기록하고, 월말에 얼마인지 계산하고, 안 보낸 사람에게 대신 말해주는 것까지가 앱의 일이에요.
            실제 송금은 각자 쓰던 방식으로 직접 합니다. 저희가 돈을 보관하거나 환급하지 않아요.
          </Text>
        </View>
      </View>

      {/* 마무리 CTA */}
      <View style={{ width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, marginTop: 46, alignItems: "center", gap: 14 }}>
        <Text style={[ui.display, { fontSize: isWide ? 28 : 23, textAlign: "center" }]}>
          이번 주부터 같이 해볼까요?
        </Text>
        <Text style={{ fontSize: 14, color: t.sub, textAlign: "center", lineHeight: 22 }}>
          모임을 만들고 링크를 카톡방에 붙이면 끝이에요.
        </Text>
        <Btn label="시작하기" onPress={go} style={{ alignSelf: "stretch" }} />
      </View>
    </ScrollView>
  );
}
