import { useState } from "react";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, CATEGORY_LABEL, PostCategory } from "../api";
import { Btn, NavBar, Note, Page, PageHeader } from "../components";
import { Icon } from "../Icon";
import { notify, notifyError } from "../notify";
import { t, ui } from "../ui";

export default function WriteScreen({ route, navigation }: any) {
  const scope: "town" | "crew" = route.params?.scope ?? "town";
  const crewId: string | undefined = route.params?.crewId;
  const [category, setCategory] = useState<PostCategory>(scope === "crew" ? "notice" : "question");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const [busy, setBusy] = useState(false);

  const cats: PostCategory[] = scope === "crew" ? ["notice", "tip", "question"] : ["question", "tip", "news"];

  const submit = async () => {
    if (busy) return;
    if (!title.trim() || !body.trim()) {
      notify("조금만 더", "제목과 내용을 채워주세요", "error");
      return;
    }
    setBusy(true);
    try {
      await api.post("/posts", {
        scope,
        crew_id: crewId ?? null,
        category,
        title: title.trim(),
        body: body.trim(),
        anonymous: scope === "town" ? anonymous : false,
      });
      notify("올렸어요", scope === "town" ? "동네 이웃들이 볼 수 있어요" : "모임 멤버들이 볼 수 있어요", "success");
      navigation.goBack();
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page nav={<NavBar navigation={navigation} />}>
      <PageHeader title="글쓰기" sub={scope === "town" ? "같은 동네 이웃들에게" : "모임 멤버들에게"} />

      <Text style={ui.sectionTitle}>어떤 이야기인가요?</Text>
      <View style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
        {cats.map((c) => {
          const on = c === category;
          return (
            <TouchableOpacity
              key={c}
              style={{
                paddingVertical: 11,
                paddingHorizontal: 16,
                borderRadius: 999,
                backgroundColor: on ? t.mint : t.card,
                borderWidth: 1,
                borderColor: on ? t.mint : t.border,
              }}
              onPress={() => setCategory(c)}
            >
              <Text style={{ fontSize: 13, fontWeight: on ? "700" : "400", color: on ? "#fff" : t.sub }}>
                {CATEGORY_LABEL[c]}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <Text style={ui.sectionTitle}>제목</Text>
      <TextInput
        style={ui.input}
        placeholder="한 줄로 요약해주세요"
        placeholderTextColor={t.sub}
        value={title}
        onChangeText={setTitle}
        maxLength={120}
      />

      <Text style={ui.sectionTitle}>내용</Text>
      <TextInput
        style={[ui.input, { height: 180, paddingTop: 14, textAlignVertical: "top" }]}
        placeholder={
          scope === "town"
            ? "어떤 게 궁금하신가요? 비슷한 고민을 한 이웃이 답해줄 거예요."
            : "모임 멤버들에게 알릴 내용을 적어주세요."
        }
        placeholderTextColor={t.sub}
        value={body}
        onChangeText={setBody}
        multiline
        maxLength={4000}
      />

      {scope === "town" && (
        <TouchableOpacity
          style={[ui.card, { flexDirection: "row", alignItems: "center", gap: 12, marginTop: 12 }]}
          onPress={() => setAnonymous(!anonymous)}
        >
          <View
            style={{
              width: 24,
              height: 24,
              borderRadius: 8,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: anonymous ? t.mint : t.bg,
              borderWidth: anonymous ? 0 : 1.5,
              borderColor: t.border,
            }}
          >
            {anonymous && <Icon name="check" size={14} color="#fff" width={2.6} />}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: "700", color: t.ink }}>익명으로 쓰기</Text>
            <Text style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>말하기 어려운 고민도 편하게</Text>
          </View>
        </TouchableOpacity>
      )}

      <Btn label={busy ? "올리는 중…" : "올리기"} onPress={submit} />
      <Note icon="shield">
        {scope === "town"
          ? "동네 글은 글자만 올릴 수 있어요. 아이 사진이나 모임 기록은 동네로 나가지 않습니다."
          : "모임 글은 이 모임 멤버만 볼 수 있어요."}
      </Note>
    </Page>
  );
}
