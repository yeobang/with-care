import { useCallback, useState } from "react";
import { useFocusEffect } from "@react-navigation/native";
import { Text, TextInput, TouchableOpacity, View } from "react-native";
import { api, Child, signOut } from "../api";
import { Avatar, Btn, Empty, NavBar, Note, Page, PageHeader, Pill } from "../components";
import { Icon } from "../Icon";
import { notify, notifyError } from "../notify";
import { MonthPicker, SkeletonCard } from "../pickers";
import { TabBar } from "../TabBar";
import { t, ui } from "../ui";

interface Me {
  id: string;
  name: string;
  identity_verified: boolean;
}

/** 내 정보 — 프로필·아이 관리·계정. 모든 앱에 있어야 하는 자리. */
export default function MeScreen({ navigation }: any) {
  const [me, setMe] = useState<Me | null>(null);
  const [children, setChildren] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftBirth, setDraftBirth] = useState("");
  const [myName, setMyName] = useState("");

  const load = useCallback(() => {
    api.get<Me>("/me").then((u) => { setMe(u); setMyName(u.name); }).catch(() => {});
    api.get<Child[]>("/my/children").then(setChildren).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useFocusEffect(load);

  const act = (fn: () => Promise<unknown>) => async () => {
    try {
      await fn();
      load();
    } catch (e: any) {
      notifyError(e);
    }
  };

  const saveName = act(async () => {
    if (!myName.trim()) return;
    await api.patch("/me", { name: myName.trim() });
    notify("저장했어요", "이름이 바뀌었어요", "success");
  });

  const startEdit = (c: Child) => {
    setEditing(c.id);
    setDraftName(c.name);
    setDraftBirth(c.birth_year_month);
  };

  const saveChild = act(async () => {
    if (!editing) return;
    await api.patch(`/my/children/${editing}`, { name: draftName.trim(), birth_year_month: draftBirth });
    setEditing(null);
    notify("수정했어요", "아이 정보가 바뀌면 모임에 다시 동의가 필요해요", "success");
  });

  const logout = async () => {
    await signOut();
    navigation.reset({ index: 0, routes: [{ name: "Landing" }] });
  };

  return (
    <View style={{ flex: 1, backgroundColor: t.bg }}>
      <Page wide nav={<NavBar navigation={navigation} />}>
        <PageHeader title="내 정보" sub="프로필과 아이 정보를 관리해요" />

        {loading && <SkeletonCard lines={2} />}

        {me && (
          <View style={ui.card}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 14 }}>
              <Avatar id={me.id} label={me.name} size={52} />
              <View style={{ flex: 1 }}>
                <Text style={ui.cardTitle}>{me.name}</Text>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 6 }}>
                  <Icon name="shield" size={14} color={me.identity_verified ? t.mintDeep : t.sub} />
                  <Text style={{ fontSize: 12, color: me.identity_verified ? t.mintDeep : t.sub }}>
                    {me.identity_verified ? "본인인증 완료" : "본인인증 전"}
                  </Text>
                </View>
              </View>
            </View>
            <View style={{ flexDirection: "row", gap: 8, marginTop: 14, alignItems: "flex-start" }}>
              <TextInput
                style={[ui.input, { flex: 1, marginTop: 0 }]}
                value={myName}
                onChangeText={setMyName}
                placeholder="이름"
                placeholderTextColor={t.sub}
              />
              <Btn label="저장" tone="soft" style={{ width: 88, marginTop: 0 }} onPress={saveName} />
            </View>
          </View>
        )}

        <Text style={ui.sectionTitle}>우리 아이</Text>
        {!loading && children.length === 0 && (
          <Empty icon="heart" title="등록된 아이가 없어요" body="홈에서 아이를 먼저 등록해주세요." />
        )}
        {children.map((c) => (
          <View key={c.id} style={ui.card}>
            {editing === c.id ? (
              <View style={{ gap: 10 }}>
                <TextInput style={ui.input} value={draftName} onChangeText={setDraftName} placeholder="이름" placeholderTextColor={t.sub} />
                <MonthPicker value={draftBirth} onChange={setDraftBirth} />
                <View style={{ flexDirection: "row", gap: 8 }}>
                  <Btn label="저장" style={{ flex: 1 }} onPress={saveChild} />
                  <Btn label="취소" tone="ghost" style={{ width: 90 }} onPress={() => setEditing(null)} />
                </View>
              </View>
            ) : (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
                <Avatar id={c.id} label={c.name} size={42} />
                <View style={{ flex: 1 }}>
                  <Text style={ui.cardTitle}>{c.name}</Text>
                  <Text style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>
                    {c.birth_year_month.slice(0, 4)}년 {Number(c.birth_year_month.slice(5, 7))}월
                  </Text>
                </View>
                <TouchableOpacity
                  style={{ paddingVertical: 10, paddingHorizontal: 14, borderRadius: 12, backgroundColor: t.bg }}
                  onPress={() => startEdit(c)}
                >
                  <Text style={{ fontSize: 13, fontWeight: "700", color: t.sub }}>수정</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        ))}
        <Note icon="shield">
          아이 정보(알레르기·투약 등)를 고치면 모임의 약속 확인을 다시 해야 해요. 다른 집이 최신 정보를 모른 채
          아이를 맡는 일이 없도록요.
        </Note>

        <Text style={ui.sectionTitle}>계정</Text>
        <View style={ui.card}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <Text style={{ fontSize: 14, color: t.sub }}>알림</Text>
            <Pill label="푸시 켜짐" tone="mint" />
          </View>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <Text style={{ fontSize: 14, color: t.sub }}>버전</Text>
            <Text style={{ fontSize: 14, color: t.ink }}>1.0.0</Text>
          </View>
        </View>
        <Btn label="로그아웃" tone="ghost" onPress={logout} />
      </Page>
      <TabBar navigation={navigation} active="me" />
    </View>
  );
}
