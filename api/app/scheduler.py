"""주기 작업 (P7): 독촉·보드 리마인드 — "조르기는 전자동".

가정 (크루 규약 아님, 전역 기본값 — 추후 규약 항목화 후보):
- 매일 09:00 KST: 미정산 독촉
- 일요일 18:00 KST: 다음 주 보드 입력 리마인드

settings.scheduler_enabled 로 켠다 (테스트·마이그레이션 실행 시 꺼짐이 기본).
"""

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


def _with_session(fn):
    from app.deps import _SessionLocal

    def run():
        db = _SessionLocal()
        try:
            fn(db)
            db.commit()
        except Exception:
            db.rollback()
            log.warning("스케줄 작업 실패 — 다음 주기에 재시도", exc_info=True)
        finally:
            db.close()

    return run


def start_scheduler() -> BackgroundScheduler:
    from app import notifications

    sched = BackgroundScheduler(timezone=KST)
    sched.add_job(_with_session(notifications.nudge_all_pending), "cron", hour=9, minute=0)
    sched.add_job(
        _with_session(notifications.remind_weekly_board),
        "cron", day_of_week="sun", hour=18, minute=0,
    )
    sched.start()
    return sched
