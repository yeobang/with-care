# with-care

**친한 부모들 카톡방 옆에 붙는 총무 앱.** 크루(3~6가구 신뢰 단위)의 주간 돌봄 조율·크레딧
장부·정산을 대신하고, 빈칸은 시터 공동고용으로 폴백한다. 핵심 테제: **악역의 자동화** —
조르기(독촉·리마인드·벌금 고지)·계산·기록은 앱이, 고르기(배정·시터 확정)는 사람이.

- 스택: Expo RN(TS) 앱 + Expo Web 현관 / FastAPI(Python) / Supabase(관리형 Postgres·Auth·Storage — 인프라로만)
- 문서: [docs/00-ideation.md](docs/00-ideation.md)(결정 대장 §17~§25) ·
  [docs/02-guardrails.md](docs/02-guardrails.md)(불변식 I1~I8) · [docs/03-dev-plan.md](docs/03-dev-plan.md)(로드맵)

## 실행 방법

사전 준비: Python 3.11+ (uv 권장), Node 22+.

```bash
# 1) API
cd api
uv venv -p 3.11 .venv
uv pip install -p .venv/bin/python -r requirements.txt
cp .env.example .env          # Supabase URL·키·DB URI 채우기 (Session pooler + postgresql+psycopg://)
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --port 8000

# 2) 테스트 (외부 의존 없음 — SQLite in-memory + 모킹, 86개)
.venv/bin/python -m pytest

# 3) 앱 (웹)
cd ../app
npm ci
cp .env.example .env          # EXPO_PUBLIC_SUPABASE_* 비우면 dev 헤더 인증 폴백
npm run web                   # http://localhost:8081
```

인증: Supabase 환경변수가 있으면 이메일 OTP(JWT), 없으면 dev 전용 `X-User-Id` 헤더 폴백.
prod(`ENV=prod`)에서는 JWT만 허용된다.

## 핵심 설계 판단

- **불변식 8개가 곧 제품이다** — 본인인증+초대 없이는 인계 불가(I1), 포괄 합의 없이는 활동
  불가(I2), 무인가 보육 패턴 차단(I3), 고르기는 사람(I4: 모든 확정은 각 가정의 명시적 탭),
  이웃 트랙의 돈은 만지지 않음(I5: 결제·이체 코드 부재를 정적 테스트로 강제), 크루 데이터
  격리(I6), 규약 없는 크루는 비활성(I7), 연령 분기 금지(I8). **전부 자동 테스트로 강제.**
- **도메인 규칙은 FastAPI에만** — 앱은 Supabase에 직접 쓰지 않고, RLS는 심층 방어(deny-all)로만.
- **장부는 아이·시간 제로섬**(§21), 정산 확정은 반대 부호 상쇄 기입(§22 — 항목은 수정·삭제하지
  않는다), 호스트 사례는 원화 전용 정산 행(§24). 시터 트랙은 크레딧과 별개 축(§25).
- **알림은 전부 best-effort** — 푸시 실패가 본 흐름을 깨지 않는다(degrade). 독촉·리마인드는
  스케줄러(매일 09:00 / 일 18:00 KST)가 대신한다.

## 알려진 한계 / 하지 않은 것

- **배포 전 게이트**: API 호스팅·EAS 빌드/스토어 미배포. 본인인증(PASS)은 스텁 어댑터
  (사업자 확보 후 교체). 법률 게이트 5건(guardrails §3)은 변호사 확인 전 정식 출시 불가.
- **결제 없음(의도)**: 시터 견적도 계산·안내까지 — PG 도입은 수익화 시점 별도 결정.
- 100배 규모 시 첫 병목: `propose`의 가능×필요 매칭(크루 단위라 실사용에선 작음),
  세션 목록의 사진 서명 URL 발급(일괄화 완료, 페이지네이션은 미도입).
- 범위 밖(만들지 않음): 자유 채팅, 동네 커뮤니티, 병상보육, 크레딧 현금화, GPS 추적,
  0~2세 세션, 광고.
