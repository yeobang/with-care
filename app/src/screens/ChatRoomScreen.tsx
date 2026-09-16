import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, ChatMessage, del } from "../api";
import { Btn, NavBar } from "../components";
import { Icon } from "../Icon";
import { notifyError } from "../notify";
import { t, ui, useLayout } from "../ui";

const POLL_MS = 4000;

export default function ChatRoomScreen({ route, navigation }: any) {
  const { roomId, title } = route.params;
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef<ScrollView>(null);
  const { contentMax } = useLayout();

  const load = useCallback(async () => {
    try {
      const rows = await api.get<ChatMessage[]>(`/chat/rooms/${roomId}/messages?limit=100`);
      setMsgs(rows);
    } catch {
      // 폴링 실패는 조용히 — 다음 주기에 다시 시도 (degrade)
    }
  }, [roomId]);

  useFocusEffect(
    useCallback(() => {
      load();
      const timer = setInterval(load, POLL_MS);
      return () => clearInterval(timer);
    }, [load]),
  );

  useEffect(() => {
    setTimeout(() => scroller.current?.scrollToEnd({ animated: false }), 60);
  }, [msgs.length]);

  const send = async () => {
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    setText("");
    try {
      await api.post(`/chat/rooms/${roomId}/messages`, { body });
      await load();
    } catch (e) {
      notifyError(e);
      setText(body); // 실패하면 입력을 돌려준다
    } finally {
      setBusy(false);
    }
  };

  const remove = async (m: ChatMessage) => {
    try {
      await del(`/chat/messages/${m.id}`);
      load();
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <View style={{ width: "100%", maxWidth: contentMax, alignSelf: "center", paddingHorizontal: 20 }}>
        <NavBar navigation={navigation} />
        <Text style={[ui.cardTitle, { fontSize: 18, marginBottom: 6 }]}>{title ?? "대화"}</Text>
      </View>

      <ScrollView
        ref={scroller}
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 20, paddingBottom: 10, width: "100%", maxWidth: contentMax, alignSelf: "center" }}
      >
        {msgs.length === 0 && (
          <Text style={[ui.hint, { textAlign: "center", marginTop: 40 }]}>
            첫 메시지를 남겨보세요
          </Text>
        )}
        {msgs.map((m) => {
          const me = m.sender.is_me;
          return (
            <View key={m.id} style={{ alignItems: me ? "flex-end" : "flex-start", marginBottom: 12 }}>
              {!me && <Text style={{ fontSize: 11, color: t.sub, marginBottom: 4 }}>{m.sender.name}</Text>}
              <TouchableOpacity
                activeOpacity={me && !m.deleted ? 0.6 : 1}
                onLongPress={() => me && !m.deleted && remove(m)}
                style={{
                  maxWidth: "82%",
                  backgroundColor: m.deleted ? t.bg : me ? t.mint : t.card,
                  borderWidth: me && !m.deleted ? 0 : 1,
                  borderColor: t.border,
                  borderRadius: 18,
                  borderBottomRightRadius: me ? 6 : 18,
                  borderBottomLeftRadius: me ? 18 : 6,
                  paddingVertical: 11,
                  paddingHorizontal: 15,
                }}
              >
                <Text
                  style={{
                    fontSize: 15,
                    lineHeight: 22,
                    color: m.deleted ? t.sub : me ? "#fff" : t.ink,
                    fontStyle: m.deleted ? "italic" : "normal",
                  }}
                >
                  {m.body}
                </Text>
              </TouchableOpacity>
              <Text style={{ fontSize: 10, color: t.sub, marginTop: 4 }}>
                {new Date(m.created_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
              </Text>
            </View>
          );
        })}
      </ScrollView>

      <View style={{ borderTopWidth: 1, borderTopColor: t.border, backgroundColor: t.card, paddingBottom: 18 }}>
        <View style={{ width: "100%", maxWidth: contentMax, alignSelf: "center", padding: 12, flexDirection: "row", gap: 8, alignItems: "flex-end" }}>
          <TextInput
            style={[ui.input, { flex: 1, marginTop: 0, backgroundColor: t.bg }]}
            placeholder="메시지를 입력하세요"
            placeholderTextColor={t.sub}
            value={text}
            onChangeText={setText}
            onSubmitEditing={send}
            returnKeyType="send"
            multiline
          />
          <TouchableOpacity
            style={{ width: 52, height: 52, borderRadius: 16, backgroundColor: t.mint, alignItems: "center", justifyContent: "center" }}
            onPress={send}
          >
            <Icon name="chevron" size={22} color="#fff" width={2.4} />
          </TouchableOpacity>
        </View>
        <Text style={{ fontSize: 11, color: t.sub, textAlign: "center", marginTop: -4 }}>
          사진은 돌봄 일정에만 올릴 수 있어요 · 길게 눌러 삭제
        </Text>
      </View>
    </View>
  );
}
