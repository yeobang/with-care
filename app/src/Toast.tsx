import { useEffect, useRef, useState } from "react";
import { Animated, Text, TouchableOpacity, View } from "react-native";
import { Icon, IconName } from "./Icon";
import { setToastListener, ToastItem } from "./notify";
import { t } from "./ui";

const TONE: Record<string, { bg: string; fg: string; icon: IconName }> = {
  info: { bg: t.deep, fg: "#fff", icon: "bell" },
  success: { bg: t.mint, fg: "#fff", icon: "check" },
  error: { bg: t.coral, fg: "#fff", icon: "shield" },
};

function Row({ item, onDone }: { item: ToastItem; onDone: (id: number) => void }) {
  const anim = useRef(new Animated.Value(0)).current;
  const tone = TONE[item.tone] ?? TONE.info;

  useEffect(() => {
    Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 8 }).start();
    const timer = setTimeout(() => {
      Animated.timing(anim, { toValue: 0, duration: 180, useNativeDriver: true }).start(() => onDone(item.id));
    }, item.tone === "error" ? 5200 : 3400);
    return () => clearTimeout(timer);
  }, [anim, item, onDone]);

  return (
    <Animated.View
      style={{
        opacity: anim,
        transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-14, 0] }) }],
        backgroundColor: tone.bg,
        borderRadius: 16,
        paddingVertical: 14,
        paddingHorizontal: 16,
        marginBottom: 8,
        flexDirection: "row",
        gap: 12,
        alignItems: "flex-start",
        shadowColor: "#26332C",
        shadowOpacity: 0.18,
        shadowRadius: 18,
        shadowOffset: { width: 0, height: 8 },
        maxWidth: 420,
        width: "100%",
      }}
    >
      <Icon name={tone.icon} size={19} color={tone.fg} />
      <View style={{ flex: 1 }}>
        <Text style={{ color: tone.fg, fontWeight: "700", fontSize: 14 }}>{item.title}</Text>
        {!!item.message && (
          <Text style={{ color: tone.fg, opacity: 0.9, fontSize: 13, marginTop: 3, lineHeight: 19 }}>{item.message}</Text>
        )}
      </View>
      <TouchableOpacity onPress={() => onDone(item.id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
        <Text style={{ color: tone.fg, opacity: 0.7, fontSize: 16 }}>✕</Text>
      </TouchableOpacity>
    </Animated.View>
  );
}

/** 앱 최상단에 한 번만 올린다. */
export function ToastHost() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    setToastListener((item) => setItems((prev) => [...prev.slice(-2), item]));
    return () => setToastListener(null);
  }, []);

  if (items.length === 0) return null;
  const remove = (id: number) => setItems((prev) => prev.filter((i) => i.id !== id));

  return (
    <View
      pointerEvents="box-none"
      style={{ position: "absolute", top: 14, left: 0, right: 0, alignItems: "center", paddingHorizontal: 16, zIndex: 999 }}
    >
      {items.map((item) => (
        <Row key={item.id} item={item} onDone={remove} />
      ))}
    </View>
  );
}
