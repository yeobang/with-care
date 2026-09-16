import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, View } from "react-native";
import { api, AppNotification, timeAgo } from "../api";
import { Btn, Empty, NavBar, Page, PageHeader } from "../components";
import { Icon } from "../Icon";
import { notifyError } from "../notify";
import { SkeletonCard } from "../pickers";
import { TabBar } from "../TabBar";
import { t, ui } from "../ui";

/** 알림함 — 푸시는 놓칠 수 있으니 앱 안에 남긴다. */
export default function AlertsScreen({ navigation }: any) {
  const [rows, setRows] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    api
      .get<AppNotification[]>("/me/notifications?limit=50")
      .then(setRows)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useFocusEffect(load);

  const markRead = async () => {
    try {
      await api.post("/me/notifications/read");
      load();
    } catch (e) {
      notifyError(e);
    }
  };

  const unread = rows.filter((r) => !r.read).length;

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <Page wide nav={<NavBar navigation={navigation} />}>
        <PageHeader title="알림" sub={unread > 0 ? `읽지 않은 알림 ${unread}개` : "모두 확인했어요"} />

        {loading && <SkeletonCard lines={2} />}
        {!loading && rows.length === 0 && (
          <Empty
            icon="bell"
            title="아직 알림이 없어요"
            body={"돌봄이 정해지거나 사진이 올라오면\n여기에서 알려드릴게요."}
          />
        )}

        {rows.map((n) => (
          <View
            key={n.id}
            style={[
              ui.card,
              !n.read && { borderColor: "#CFEBE2", backgroundColor: t.mintTint, shadowOpacity: 0 },
            ]}
          >
            <View style={{ flexDirection: "row", gap: 12 }}>
              <View
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 12,
                  backgroundColor: n.read ? t.bg : t.card,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon name="bell" size={17} color={n.read ? t.sub : t.mintDeep} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: "700", color: t.ink }}>{n.title}</Text>
                <Text style={{ fontSize: 13, color: t.sub, marginTop: 4, lineHeight: 20 }}>{n.body}</Text>
                <Text style={{ fontSize: 11, color: t.sub, marginTop: 6 }}>{timeAgo(n.created_at)}</Text>
              </View>
            </View>
          </View>
        ))}

        {unread > 0 && <Btn label="모두 읽음으로 표시" tone="ghost" onPress={markRead} />}
      </Page>
      <TabBar navigation={navigation} active="alerts" />
    </View>
  );
}
