import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, CATEGORY_LABEL, Post, PostCategory, timeAgo } from "../api";
import { Avatar, Btn, Empty, NavBar, Note, Page, PageHeader } from "../components";
import { Icon } from "../Icon";
import { notify, notifyError } from "../notify";
import { SkeletonCard } from "../pickers";
import { TabBar } from "../TabBar";
import { t, ui } from "../ui";

const TABS: { key: PostCategory | "all"; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "question", label: "궁금해요" },
  { key: "tip", label: "이렇게 해요" },
  { key: "news", label: "동네 소식" },
];

export default function CommunityScreen({ navigation }: any) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [cat, setCat] = useState<PostCategory | "all">("all");
  const [loading, setLoading] = useState(true);
  const [town, setTown] = useState<string | null>(null);
  const [townInput, setTownInput] = useState("");
  const [needTown, setNeedTown] = useState(false);

  const load = useCallback(() => {
    api
      .get<{ town_name: string | null }>("/me")
      .then((me: any) => setTown(me.town_name ?? null))
      .catch(() => {});
    const q = cat === "all" ? "" : `&category=${cat}`;
    api
      .get<Post[]>(`/posts?scope=town&limit=30${q}`)
      .then((rows) => {
        setPosts(rows);
        setNeedTown(false);
      })
      .catch((e) => {
        if (/동네/.test(e.message)) setNeedTown(true);
      })
      .finally(() => setLoading(false));
  }, [cat]);
  useFocusEffect(load);

  const saveTown = async () => {
    const name = townInput.trim();
    if (!name) return;
    try {
      // 행정동 이름을 그대로 코드로 쓴다 (MVP — 행정동 코드 DB 연동 전)
      await api.patch("/me/town", { town_code: name, town_name: name });
      setTownInput("");
      notify("동네를 설정했어요", `${name} 이웃들의 글이 보여요`, "success");
      load();
    } catch (e) {
      notifyError(e);
    }
  };

  const like = async (p: Post) => {
    try {
      const r = await api.post<{ likes: number; liked: boolean }>(`/posts/${p.id}/like`);
      setPosts((prev) => prev.map((x) => (x.id === p.id ? { ...x, likes: r.likes, liked: r.liked } : x)));
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <Page wide nav={<NavBar navigation={navigation} />}>
        <PageHeader
          title="동네 이야기"
          sub={town ? `${town} 이웃들` : "같은 동네 부모들의 이야기"}
          right={
            <Btn
              label="글쓰기"
              style={{ marginTop: 0, paddingHorizontal: 18, height: 44 }}
              onPress={() => navigation.navigate("Write", { scope: "town" })}
            />
          }
        />

        {needTown && (
          <View style={[ui.card, { backgroundColor: t.lemonTint, borderColor: "#F3E4BE", shadowOpacity: 0 }]}>
            <Text style={{ fontSize: 15, fontWeight: "700", color: t.ink }}>먼저 동네를 알려주세요</Text>
            <Text style={{ fontSize: 13, color: t.lemonDeep, marginTop: 6, lineHeight: 20 }}>
              같은 동네 이웃들의 글만 보여드려요. 동(洞)까지만 받고 상세 주소는 저장하지 않아요.
            </Text>
            <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
              <TextInput
                style={[ui.input, { flex: 1 }]}
                placeholder="예: 역삼1동"
                placeholderTextColor={t.sub}
                value={townInput}
                onChangeText={setTownInput}
              />
              <Btn label="설정" style={{ width: 88 }} onPress={saveTown} />
            </View>
          </View>
        )}

        {!needTown && (
          <View style={{ flexDirection: "row", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
            {TABS.map((tab) => {
              const on = tab.key === cat;
              return (
                <TouchableOpacity
                  key={tab.key}
                  style={{
                    paddingVertical: 9,
                    paddingHorizontal: 14,
                    borderRadius: 999,
                    backgroundColor: on ? t.mint : t.card,
                    borderWidth: 1,
                    borderColor: on ? t.mint : t.border,
                  }}
                  onPress={() => setCat(tab.key)}
                >
                  <Text style={{ fontSize: 13, fontWeight: on ? "700" : "400", color: on ? "#fff" : t.sub }}>
                    {tab.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        <View style={{ height: 14 }} />
        {loading && <SkeletonCard lines={2} />}
        {!loading && !needTown && posts.length === 0 && (
          <Empty
            icon="users"
            title="아직 글이 없어요"
            body={"첫 글을 남겨보세요.\n같은 동네 부모들이 보고 답해줄 거예요."}
            action={<Btn label="글쓰기" onPress={() => navigation.navigate("Write", { scope: "town" })} />}
          />
        )}

        {posts.map((p) => (
          <TouchableOpacity key={p.id} style={ui.card} onPress={() => navigation.navigate("Post", { postId: p.id })}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <View style={{ backgroundColor: t.mintTint, borderRadius: 999, paddingVertical: 4, paddingHorizontal: 10 }}>
                <Text style={{ fontSize: 11, fontWeight: "700", color: t.mintDeep }}>{CATEGORY_LABEL[p.category]}</Text>
              </View>
              <Text style={{ fontSize: 12, color: t.sub }}>{timeAgo(p.created_at)}</Text>
            </View>
            <Text style={ui.cardTitle}>{p.title}</Text>
            <Text numberOfLines={2} style={{ fontSize: 13, color: t.sub, marginTop: 6, lineHeight: 20 }}>
              {p.body}
            </Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 14, marginTop: 12 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                <Avatar id={p.author.id ?? "anon"} label={p.author.name} size={22} />
                <Text style={{ fontSize: 12, color: t.sub }}>{p.author.name}</Text>
              </View>
              <TouchableOpacity style={{ flexDirection: "row", alignItems: "center", gap: 5 }} onPress={() => like(p)}>
                <Icon name="heart" size={15} color={p.liked ? t.coral : t.sub} width={p.liked ? 2.4 : 1.8} />
                <Text style={{ fontSize: 12, color: p.liked ? t.coralDeep : t.sub }}>{p.likes}</Text>
              </TouchableOpacity>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
                <Icon name="brief" size={15} color={t.sub} />
                <Text style={{ fontSize: 12, color: t.sub }}>{p.comment_count}</Text>
              </View>
            </View>
          </TouchableOpacity>
        ))}

        {!needTown && posts.length > 0 && (
          <Note icon="shield">
            아이 사진이나 모임의 장부·기록은 동네 글에 올라가지 않아요. 공개 글은 글자만 쓸 수 있습니다.
          </Note>
        )}
      </Page>
      <TabBar navigation={navigation} active="town" />
    </View>
  );
}
