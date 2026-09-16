import { useEffect, useState } from "react";
import { Text, TouchableOpacity, View } from "react-native";
import { api, AppNotification } from "./api";
import { Icon, IconName } from "./Icon";
import { t, useLayout } from "./ui";

export type TabKey = "home" | "crews" | "alerts" | "me";

const TABS: { key: TabKey; label: string; icon: IconName; screen: string }[] = [
  { key: "home", label: "홈", icon: "home", screen: "Home" },
  { key: "crews", label: "모임", icon: "users", screen: "Home" },
  { key: "alerts", label: "알림", icon: "bell", screen: "Alerts" },
  { key: "me", label: "내 정보", icon: "heart", screen: "Me" },
];

/** 모바일 하단 탭 — 앱의 뼈대. 넓은 화면에서는 상단 NavBar가 대신한다. */
export function TabBar({ navigation, active }: { navigation: any; active: TabKey }) {
  const { isWide } = useLayout();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    api
      .get<AppNotification[]>("/me/notifications?limit=30")
      .then((rows) => setUnread(rows.filter((r) => !r.read).length))
      .catch(() => {});
  }, [active]);

  if (isWide) return null;

  return (
    <View
      style={{
        flexDirection: "row",
        borderTopWidth: 1,
        borderTopColor: t.border,
        backgroundColor: t.card,
        paddingBottom: 18,
        paddingTop: 8,
      }}
    >
      {TABS.map((tab) => {
        const on = tab.key === active;
        return (
          <TouchableOpacity
            key={tab.key}
            style={{ flex: 1, alignItems: "center", gap: 3, paddingVertical: 4 }}
            onPress={() => navigation.navigate(tab.screen)}
          >
            <View>
              <Icon name={tab.icon} size={22} color={on ? t.mintDeep : t.sub} width={on ? 2.2 : 1.8} />
              {tab.key === "alerts" && unread > 0 && (
                <View
                  style={{
                    position: "absolute",
                    top: -4,
                    right: -8,
                    minWidth: 17,
                    height: 17,
                    borderRadius: 999,
                    backgroundColor: t.coral,
                    alignItems: "center",
                    justifyContent: "center",
                    paddingHorizontal: 4,
                  }}
                >
                  <Text style={{ fontSize: 10, color: "#fff", fontWeight: "700" }}>{unread > 9 ? "9+" : unread}</Text>
                </View>
              )}
            </View>
            <Text style={{ fontSize: 11, fontWeight: on ? "700" : "400", color: on ? t.mintDeep : t.sub }}>{tab.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}
