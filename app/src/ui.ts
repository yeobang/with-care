import { Platform, StyleSheet, useWindowDimensions } from "react-native";

/**
 * 디자인 토큰 — "플레이풀 파스텔" (docs 디자인 캔버스 확정 방향).
 * 돈·규약이 걸린 화면(장부 헤더·규약 카드)만 deep 톤으로 눌러 가볍지 않게 잡는다.
 */
export const t = {
  bg: "#FDFBF4",
  card: "#FFFFFF",
  border: "#E7EDE6",
  ink: "#26332C",
  sub: "#7C8A80",
  mint: "#4FB79A",
  mintTint: "#E4F4EF",
  mintDeep: "#2F8C74",
  lemon: "#F2C14E",
  lemonTint: "#FDF3DC",
  lemonDeep: "#9A7412",
  coral: "#F0836B",
  coralTint: "#FDEAE5",
  coralDeep: "#C25A44",
  lilac: "#9B8CD6",
  lilacTint: "#EFECFA",
  deep: "#1F3A34", // 정산·규약 등 무게가 필요한 면
  deepSub: "#8FA9A1",
};

/** 웹에서만 커스텀 폰트 (public/index.html에서 로드). 네이티브는 시스템 폰트 폴백. */
const bodyFont = Platform.select({
  web: "'IBM Plex Sans KR', 'Apple SD Gothic Neo', system-ui, sans-serif",
  default: undefined,
});
const displayFont = Platform.select({
  web: "'Jua', 'IBM Plex Sans KR', 'Apple SD Gothic Neo', system-ui, sans-serif",
  default: undefined,
});

/** 브레이크포인트: 모바일 / 태블릿 / 데스크톱 */
export function useLayout() {
  const { width } = useWindowDimensions();
  return {
    width,
    isWide: width >= 900, // 데스크톱 2단 레이아웃
    isTablet: width >= 640 && width < 900,
    contentMax: width >= 900 ? 1180 : width >= 640 ? 640 : 560,
  };
}

export const ui = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: t.bg,
    padding: 24,
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    maxWidth: 480,
    alignSelf: "center",
  },
  screen: {
    flex: 1,
    backgroundColor: t.bg,
    paddingHorizontal: 20,
    paddingTop: 8,
    width: "100%",
    alignSelf: "center",
  },
  title: { fontSize: 30, fontFamily: displayFont, fontWeight: Platform.OS === "web" ? "400" : "700", color: t.ink },
  display: { fontFamily: displayFont, color: t.ink },
  subtitle: { fontSize: 14, color: t.sub, marginTop: 5, fontFamily: bodyFont },
  hint: { fontSize: 12, color: t.sub, marginTop: 10, lineHeight: 18, fontFamily: bodyFont },
  sectionTitle: { fontSize: 17, fontWeight: "700", marginTop: 22, marginBottom: 10, color: t.ink, fontFamily: bodyFont },
  text: { fontFamily: bodyFont, color: t.ink },

  card: {
    borderWidth: 1,
    borderColor: t.border,
    borderRadius: 20,
    padding: 18,
    marginBottom: 12,
    backgroundColor: t.card,
    shadowColor: "#26332C",
    shadowOpacity: 0.05,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
    elevation: 1,
  },
  cardTitle: { fontSize: 17, fontWeight: "700", color: t.ink, fontFamily: bodyFont },

  primaryBtn: {
    backgroundColor: t.mint,
    borderRadius: 16,
    height: 52,
    paddingHorizontal: 20,
    marginTop: 12,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: t.mint,
    shadowOpacity: 0.32,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  primaryBtnText: { color: "#fff", fontWeight: "700", fontSize: 15, fontFamily: bodyFont },
  softBtn: {
    backgroundColor: t.mintTint,
    borderRadius: 16,
    height: 52,
    paddingHorizontal: 20,
    marginTop: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  softBtnText: { color: t.mintDeep, fontWeight: "700", fontSize: 15, fontFamily: bodyFont },

  smallBtn: {
    backgroundColor: t.card,
    borderWidth: 1,
    borderColor: t.border,
    borderRadius: 14,
    minHeight: 44,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginRight: 8,
    marginTop: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  smallBtnActive: { backgroundColor: t.mint, borderColor: t.mint },
  smallBtnText: { fontSize: 13, color: t.ink, fontWeight: "600", fontFamily: bodyFont },
  smallBtnTextActive: { color: "#fff" },

  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center" },
  input: {
    borderWidth: 1.5,
    borderColor: t.border,
    borderRadius: 16,
    paddingHorizontal: 16,
    height: 52,
    marginTop: 8,
    backgroundColor: t.card,
    color: t.ink,
    fontSize: 15,
    fontFamily: bodyFont,
  },
  pill: {
    paddingVertical: 5,
    paddingHorizontal: 12,
    borderRadius: 999,
    alignSelf: "flex-start",
  },
  pillText: { fontSize: 12, fontWeight: "700", fontFamily: bodyFont },
  avatar: {
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { color: "#fff", fontWeight: "700", fontFamily: bodyFont },
});

/** 크루/사용자 id로 안정적인 파스텔 색 — 아바타·범례용 */
const PALETTE = [t.mint, t.lemon, t.coral, t.lilac];
export function tintFor(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}
