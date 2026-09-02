#!/usr/bin/env bash
# with-care 배포 (P11): Fly.io — API + 웹 현관. 사전: fly auth login 완료.
set -euo pipefail
cd "$(dirname "$0")/.."

API_APP="with-care-api"
WEB_APP="with-care-web"
API_URL="https://${API_APP}.fly.dev"
WEB_URL="https://${WEB_APP}.fly.dev"

case "${1:-all}" in
  api|all)
    echo "== API 배포 (${API_APP}) — release에서 alembic upgrade head 실행 =="
    (cd api && fly deploy --remote-only)
    ;;&
  web|all)
    echo "== 웹 현관 빌드 (API_URL=${API_URL}) =="
    (cd app && EXPO_PUBLIC_API_URL="$API_URL" \
      EXPO_PUBLIC_SUPABASE_URL="https://knfwblfrmpochzaarvtq.supabase.co" \
      EXPO_PUBLIC_SUPABASE_KEY="sb_publishable_rIWoJmWxNEfbW2CTzNdGmA_UujfAV09" \
      npx expo export --platform web)
    echo "== 웹 배포 (${WEB_APP}) =="
    (cd app && fly deploy --remote-only --config fly.web.toml)
    echo "웹 현관: ${WEB_URL} — CORS_ORIGINS가 이 URL을 포함해야 함 (api/fly.toml)"
    ;;
esac
