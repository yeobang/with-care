import { ReactNode } from "react";
import { ScrollView, Text, TouchableOpacity, View, ViewStyle } from "react-native";
import { t, tintFor, ui, useLayout } from "./ui";

/** 넓은 화면에서 중앙 정렬 + 최대폭 제한. 모든 화면의 바깥 껍데기. */
export function Page({ children, wide }: { children?: ReactNode; wide?: boolean }) {
  const { contentMax } = useLayout();
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: t.bg }}
      contentContainerStyle={{ paddingBottom: 48, paddingHorizontal: 20, paddingTop: 12 }}
    >
      <View style={{ width: "100%", maxWidth: wide ? contentMax : Math.min(contentMax, 640), alignSelf: "center" }}>
        {children}
      </View>
    </ScrollView>
  );
}

/** 데스크톱에서 좌우 2단, 좁은 화면에서 세로 스택. */
export function Columns({
  left,
  right,
  ratio = 1.5,
}: {
  left: ReactNode;
  right: ReactNode;
  ratio?: number;
}) {
  const { isWide } = useLayout();
  if (!isWide) {
    return (
      <View>
        {left}
        {right}
      </View>
    );
  }
  return (
    <View style={{ flexDirection: "row", gap: 20, alignItems: "flex-start" }}>
      <View style={{ flex: ratio }}>{left}</View>
      <View style={{ flex: 1 }}>{right}</View>
    </View>
  );
}

export function PageHeader({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <View
      style={{
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "flex-end",
        marginTop: 14,
        marginBottom: 6,
        gap: 12,
      }}
    >
      <View style={{ flexShrink: 1 }}>
        <Text style={ui.title}>{title}</Text>
        {!!sub && <Text style={ui.subtitle}>{sub}</Text>}
      </View>
      {right}
    </View>
  );
}

export function Pill({ label, tone = "mint" }: { label: string; tone?: "mint" | "lemon" | "coral" | "neutral" }) {
  const map = {
    mint: [t.mintDeep, t.mintTint],
    lemon: [t.lemonDeep, t.lemonTint],
    coral: [t.coralDeep, t.coralTint],
    neutral: [t.sub, t.bg],
  } as const;
  const [fg, bg] = map[tone];
  return (
    <View style={[ui.pill, { backgroundColor: bg }]}>
      <Text style={[ui.pillText, { color: fg }]}>{label}</Text>
    </View>
  );
}

export function Avatar({ id, label, size = 34 }: { id: string; label: string; size?: number }) {
  return (
    <View style={[ui.avatar, { width: size, height: size, backgroundColor: tintFor(id) }]}>
      <Text style={[ui.avatarText, { fontSize: Math.round(size * 0.42) }]}>{label.slice(0, 1)}</Text>
    </View>
  );
}

export function Btn({
  label,
  onPress,
  tone = "mint",
  style,
}: {
  label: string;
  onPress?: () => void;
  tone?: "mint" | "soft" | "coral" | "ghost" | "deep";
  style?: ViewStyle;
}) {
  const tones: Record<string, [ViewStyle, string]> = {
    mint: [ui.primaryBtn, "#fff"],
    soft: [ui.softBtn, t.mintDeep],
    coral: [{ ...ui.primaryBtn, backgroundColor: t.coral, shadowColor: t.coral }, "#fff"],
    deep: [{ ...ui.primaryBtn, backgroundColor: t.deep, shadowColor: t.deep }, "#fff"],
    ghost: [
      { ...ui.primaryBtn, backgroundColor: t.card, borderWidth: 1.5, borderColor: t.border, shadowOpacity: 0 },
      t.sub,
    ],
  };
  const [box, color] = tones[tone];
  return (
    <TouchableOpacity style={[box, style]} onPress={onPress}>
      <Text style={[ui.primaryBtnText, { color }]}>{label}</Text>
    </TouchableOpacity>
  );
}

/** 상단 요약 타일 (데스크톱에서 가로 3열, 모바일에서 세로) */
export function StatTiles({ items }: { items: { label: string; value: string; note?: string; tone: "mint" | "coral" | "lemon" }[] }) {
  const { isWide } = useLayout();
  const bg = { mint: t.mintTint, coral: t.coralTint, lemon: t.lemonTint };
  const bd = { mint: "#CFEBE2", coral: "#F8D9D1", lemon: "#F3E4BE" };
  return (
    <View style={{ flexDirection: isWide ? "row" : "column", gap: 12, marginTop: 16 }}>
      {items.map((it) => (
        <View
          key={it.label}
          style={[ui.card, { flex: isWide ? 1 : undefined, marginBottom: isWide ? 0 : 12, backgroundColor: bg[it.tone], borderColor: bd[it.tone], shadowOpacity: 0 }]}
        >
          <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub }}>{it.label}</Text>
          <Text style={{ fontSize: 21, fontWeight: "700", color: t.ink, marginTop: 6 }}>{it.value}</Text>
          {!!it.note && <Text style={{ fontSize: 12, color: t.sub, marginTop: 4 }}>{it.note}</Text>}
        </View>
      ))}
    </View>
  );
}
