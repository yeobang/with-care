import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, CATEGORY_LABEL, del, Post, PostComment, timeAgo } from "../api";
import { Avatar, Btn, NavBar, Page } from "../components";
import { Icon } from "../Icon";
import { notify, notifyError } from "../notify";
import { SkeletonCard } from "../pickers";
import { t, ui } from "../ui";

interface Detail extends Post {
  comments: PostComment[];
}

export default function PostScreen({ route, navigation }: any) {
  const { postId } = route.params;
  const [post, setPost] = useState<Detail | null>(null);
  const [text, setText] = useState("");
  const [anon, setAnon] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get<Detail>(`/posts/${postId}`).then(setPost).catch((e) => notifyError(e));
  }, [postId]);
  useFocusEffect(load);

  const send = async () => {
    if (busy || !text.trim()) return;
    setBusy(true);
    try {
      await api.post(`/posts/${postId}/comments`, { body: text.trim(), anonymous: anon });
      setText("");
      load();
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const like = async () => {
    try {
      const r = await api.post<{ likes: number; liked: boolean }>(`/posts/${postId}/like`);
      setPost((p) => (p ? { ...p, likes: r.likes, liked: r.liked } : p));
    } catch (e) {
      notifyError(e);
    }
  };

  const remove = async () => {
    try {
      await del(`/posts/${postId}`);
      notify("지웠어요", undefined, "success");
      navigation.goBack();
    } catch (e) {
      notifyError(e);
    }
  };

  if (!post)
    return (
      <Page nav={<NavBar navigation={navigation} />}>
        <SkeletonCard lines={3} />
      </Page>
    );

  return (
    <Page nav={<NavBar navigation={navigation} />}>
      <View style={[ui.card, { marginTop: 10 }]}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <View style={{ backgroundColor: t.mintTint, borderRadius: 999, paddingVertical: 4, paddingHorizontal: 10 }}>
            <Text style={{ fontSize: 11, fontWeight: "700", color: t.mintDeep }}>{CATEGORY_LABEL[post.category]}</Text>
          </View>
          <Text style={{ fontSize: 12, color: t.sub }}>{timeAgo(post.created_at)}</Text>
          {post.author.is_me && (
            <TouchableOpacity onPress={remove} style={{ marginLeft: "auto" }}>
              <Text style={{ fontSize: 12, color: t.coralDeep }}>삭제</Text>
            </TouchableOpacity>
          )}
        </View>
        <Text style={[ui.cardTitle, { fontSize: 19 }]}>{post.title}</Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10 }}>
          <Avatar id={post.author.id ?? "anon"} label={post.author.name} size={28} />
          <Text style={{ fontSize: 13, color: t.sub }}>
            {post.author.name}
            {post.town_name ? ` · ${post.town_name}` : ""}
          </Text>
        </View>
        <Text style={{ fontSize: 15, color: t.ink, marginTop: 14, lineHeight: 25 }}>{post.body}</Text>
        <TouchableOpacity
          style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 16, alignSelf: "flex-start" }}
          onPress={like}
        >
          <Icon name="heart" size={18} color={post.liked ? t.coral : t.sub} width={post.liked ? 2.4 : 1.8} />
          <Text style={{ fontSize: 13, color: post.liked ? t.coralDeep : t.sub, fontWeight: post.liked ? "700" : "400" }}>
            공감 {post.likes}
          </Text>
        </TouchableOpacity>
      </View>

      <Text style={ui.sectionTitle}>댓글 {post.comments.length}</Text>
      {post.comments.length === 0 && (
        <Text style={ui.hint}>첫 댓글을 남겨보세요 — 비슷한 고민을 한 이웃에게 큰 힘이 돼요</Text>
      )}
      {post.comments.map((c) => (
        <View key={c.id} style={[ui.card, { padding: 14 }]}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <Avatar id={c.author.id ?? "anon"} label={c.author.name} size={24} />
            <Text style={{ fontSize: 13, fontWeight: "700", color: t.ink }}>{c.author.name}</Text>
            <Text style={{ fontSize: 11, color: t.sub }}>{timeAgo(c.created_at)}</Text>
          </View>
          <Text style={{ fontSize: 14, color: t.ink, marginTop: 8, lineHeight: 21 }}>{c.body}</Text>
        </View>
      ))}

      <View style={{ marginTop: 6 }}>
        <TextInput
          style={[ui.input, { height: 90, paddingTop: 12, textAlignVertical: "top" }]}
          placeholder="따뜻한 한마디를 남겨주세요"
          placeholderTextColor={t.sub}
          value={text}
          onChangeText={setText}
          multiline
        />
        <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
          {post.scope === "town" && (
            <TouchableOpacity
              style={{ flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 12 }}
              onPress={() => setAnon(!anon)}
            >
              <View
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: 7,
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: anon ? t.mint : t.bg,
                  borderWidth: anon ? 0 : 1.5,
                  borderColor: t.border,
                }}
              >
                {anon && <Icon name="check" size={12} color="#fff" width={2.6} />}
              </View>
              <Text style={{ fontSize: 13, color: t.sub }}>익명</Text>
            </TouchableOpacity>
          )}
          <Btn label={busy ? "올리는 중…" : "댓글 달기"} style={{ flex: 1 }} onPress={send} />
        </View>
      </View>
    </Page>
  );
}
