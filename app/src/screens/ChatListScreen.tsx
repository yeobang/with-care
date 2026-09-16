import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TouchableOpacity, View } from "react-native";
import { api, ChatRoomSummary, timeAgo } from "../api";
import { Avatar, Empty, NavBar, Page, PageHeader } from "../components";
import { SkeletonCard } from "../pickers";
import { TabBar } from "../TabBar";
import { t, ui } from "../ui";

export default function ChatListScreen({ navigation }: any) {
  const [rooms, setRooms] = useState<ChatRoomSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    api.get<ChatRoomSummary[]>("/chat/rooms").then(setRooms).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useFocusEffect(load);

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <Page wide nav={<NavBar navigation={navigation} />}>
        <PageHeader title="대화" sub="모임 단체방과 1:1 대화" />
        {loading && <SkeletonCard lines={2} />}
        {!loading && rooms.length === 0 && (
          <Empty
            icon="brief"
            title="아직 대화가 없어요"
            body={"모임 화면에서 단체방을 열거나,\n이웃과 1:1 대화를 시작해보세요."}
          />
        )}
        {rooms.map((r) => (
          <TouchableOpacity
            key={r.id}
            style={ui.card}
            onPress={() => navigation.navigate("ChatRoom", { roomId: r.id, title: r.title })}
          >
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <Avatar id={r.id} label={r.title || "방"} size={44} />
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <Text style={ui.cardTitle} numberOfLines={1}>
                    {r.title || r.crew_name}
                  </Text>
                  {r.kind === "crew" && !r.context_kind && (
                    <Text style={{ fontSize: 11, color: t.mintDeep, fontWeight: "700" }}>단체</Text>
                  )}
                  {r.context_kind && (
                    <Text style={{ fontSize: 11, color: t.lemonDeep, fontWeight: "700" }}>
                      {r.context_kind === "session" ? "돌봄 건" : r.context_kind === "settlement" ? "정산 건" : "후보 건"}
                    </Text>
                  )}
                </View>
                <Text numberOfLines={1} style={{ fontSize: 13, color: t.sub, marginTop: 4 }}>
                  {r.last_body ?? "아직 메시지가 없어요"}
                </Text>
              </View>
              <View style={{ alignItems: "flex-end", gap: 6 }}>
                {!!r.last_at && <Text style={{ fontSize: 11, color: t.sub }}>{timeAgo(r.last_at)}</Text>}
                {r.unread > 0 && (
                  <View style={{ minWidth: 20, height: 20, borderRadius: 999, backgroundColor: t.coral, alignItems: "center", justifyContent: "center", paddingHorizontal: 6 }}>
                    <Text style={{ fontSize: 11, color: "#fff", fontWeight: "700" }}>{r.unread > 99 ? "99+" : r.unread}</Text>
                  </View>
                )}
              </View>
            </View>
          </TouchableOpacity>
        ))}
      </Page>
      <TabBar navigation={navigation} active="chat" />
    </View>
  );
}
