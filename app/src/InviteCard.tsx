import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useState } from "react";
import { Text, TouchableOpacity, View } from "react-native";
import { api, InviteCreated, JoinRequest } from "./api";
import { Avatar, Btn } from "./components";
import { Icon } from "./Icon";
import { notify, notifyError } from "./notify";
import { copyInviteLink, inviteMessage, inviteUrl, shareInvite } from "./share";
import { t, ui } from "./ui";

/**
 * §29: 첫 사용자가 해야 할 단 하나의 행동 — 링크를 단톡방에 붙이기.
 *
 * 링크는 다회용(정원 5집)이라 한 번 만들어 재사용한다. 누를 때마다 새로 발급하면
 * 쓰이지 않는 초대가 쌓이므로 기기에 캐시해 둔다.
 */
export function InviteCard({
  crewId,
  crewName,
  memberCount,
  compact,
}: {
  crewId: string;
  crewName: string;
  memberCount: number;
  compact?: boolean;
}) {
  const key = `invite.${crewId}`;
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(key).then(setToken);
  }, [key]);

  const ensureToken = useCallback(async (): Promise<string> => {
    const cached = await AsyncStorage.getItem(key);
    if (cached) return cached;
    const r = await api.post<InviteCreated>(`/crews/${crewId}/invites`);
    await AsyncStorage.setItem(key, r.token);
    setToken(r.token);
    return r.token;
  }, [crewId, key]);

  const run = (fn: (tk: string) => Promise<void>) => async () => {
    if (busy) return;
    setBusy(true);
    try {
      await fn(await ensureToken());
    } catch (e: any) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const renew = async () => {
    setBusy(true);
    try {
      const r = await api.post<InviteCreated>(`/crews/${crewId}/invites`);
      await AsyncStorage.setItem(key, r.token);
      setToken(r.token);
      notify("새 링크를 만들었어요", "이전 링크는 그대로 두셔도 돼요", "success");
    } catch (e: any) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const short = memberCount < 3;

  return (
    <View style={[ui.card, { backgroundColor: t.mintTint, borderColor: "#CFEBE2", shadowOpacity: 0 }]}>
      <Text style={{ fontSize: 16, fontWeight: "700", color: t.ink }}>
        {short ? "이웃을 불러야 시작돼요" : "이웃 더 초대하기"}
      </Text>
      <Text style={{ fontSize: 13, color: t.sub, marginTop: 6, lineHeight: 20 }}>
        {short
          ? `지금 ${memberCount}집이에요. 3집부터 서로 맞바꿀 시간이 생겨요.\n늘 쓰는 단톡방에 링크만 붙이면 끝이에요.`
          : `지금 ${memberCount}집. 링크 하나로 최대 5집까지 들어올 수 있어요.`}
      </Text>

      <Btn label="카톡방에 붙일 문구 보내기" onPress={run(async (tk) => shareInvite(crewName, tk))} />
      <Btn label="링크만 복사하기" tone="soft" onPress={run(async (tk) => copyInviteLink(tk))} />

      {!!token && !compact && (
        <View style={{ backgroundColor: t.card, borderRadius: 14, padding: 14, marginTop: 10 }}>
          <Text style={{ fontSize: 11, fontWeight: "700", color: t.sub, marginBottom: 6 }}>
            붙여넣을 내용 미리보기
          </Text>
          <Text selectable style={{ fontSize: 12, color: t.sub, lineHeight: 19 }}>
            {inviteMessage(crewName, token)}
          </Text>
        </View>
      )}
      {!!token && (
        <Text selectable style={{ fontSize: 11, color: t.mintDeep, marginTop: 8 }}>
          {inviteUrl(token)}
        </Text>
      )}
      <Text style={{ fontSize: 11, color: t.sub, marginTop: 8, lineHeight: 17 }}>
        7일 유효 · 최대 5집 · 들어오면 회원님이 승인해야 멤버가 돼요 (모르는 사람이 들어올 수 없어요)
      </Text>
      {!!token && (
        <TouchableOpacity onPress={renew} disabled={busy} style={{ marginTop: 8 }}>
          <Text style={{ fontSize: 12, fontWeight: "700", color: t.sub }}>링크가 만료됐나요? 새로 만들기</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

/** §29: 승인 대기 줄. 다회용 링크의 안전 관문이라 눈에 띄는 자리에 둔다. */
export function JoinRequests({
  crewId,
  requests,
  onDecided,
}: {
  crewId: string;
  requests: JoinRequest[];
  onDecided: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  if (requests.length === 0) return null;

  const decide = (r: JoinRequest, approve: boolean) => async () => {
    setBusy(r.id);
    try {
      await api.post(`/crews/${crewId}/join-requests/${r.id}`, { approve });
      notify(
        approve ? `${r.name}님을 받았어요` : "거절했어요",
        approve ? "이제 함께 시간을 맞출 수 있어요" : "이 사람은 다시 신청할 수 없어요",
        "success",
      );
      onDecided();
    } catch (e: any) {
      notifyError(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <View style={[ui.card, { backgroundColor: t.lemonTint, borderColor: t.lemon, shadowOpacity: 0 }]}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Icon name="bell" size={17} color={t.lemonDeep} />
        <Text style={{ fontSize: 15, fontWeight: "700", color: t.ink }}>
          합류를 기다리는 사람 {requests.length}명
        </Text>
      </View>
      <Text style={{ fontSize: 12, color: t.sub, marginTop: 6, marginBottom: 12 }}>
        아는 분이 맞는지 확인하고 받아주세요. 승인 전에는 아무것도 볼 수 없어요.
      </Text>
      {requests.map((r) => (
        <View key={r.id} style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
          <Avatar id={r.user_id} label={r.name} size={34} />
          <View style={{ flex: 1, minWidth: 100 }}>
            <Text style={{ fontSize: 14, fontWeight: "700", color: t.ink }}>{r.name}</Text>
            <Text style={{ fontSize: 11, color: t.sub, marginTop: 2 }}>
              {r.role === "sitter" ? "시터로 신청" : "이웃으로 신청"}
            </Text>
          </View>
          <TouchableOpacity
            disabled={busy === r.id}
            onPress={decide(r, true)}
            style={{ backgroundColor: t.mint, paddingVertical: 9, paddingHorizontal: 16, borderRadius: 12 }}
          >
            <Text style={{ fontSize: 13, fontWeight: "700", color: "#fff" }}>받기</Text>
          </TouchableOpacity>
          <TouchableOpacity
            disabled={busy === r.id}
            onPress={decide(r, false)}
            style={{ paddingVertical: 9, paddingHorizontal: 12 }}
          >
            <Text style={{ fontSize: 13, color: t.sub }}>거절</Text>
          </TouchableOpacity>
        </View>
      ))}
    </View>
  );
}
