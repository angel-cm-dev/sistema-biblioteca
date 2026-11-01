from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain import policies
from app.domain.clock import Clock
from app.infrastructure.repositories.reports import ReportRepository


class ReportService:
    def __init__(self, session: Session, settings: Settings, clock: Clock) -> None:
        self.settings = settings
        self.clock = clock
        self.repo = ReportRepository(session)

    def summary(self) -> dict[str, int]:
        return self.repo.summary(self.clock.today())

    def most_borrowed(
        self, *, limit: int, date_from: date | None, date_to: date | None
    ) -> list[tuple[int, str, str, int]]:
        start = datetime.combine(date_from, time.min, UTC) if date_from else None
        # date_to es inclusivo para el usuario: filtramos < (date_to + 1 día).
        end = datetime.combine(date_to + timedelta(days=1), time.min, UTC) if date_to else None
        return self.repo.most_borrowed(limit=limit, date_from=start, date_to=end)

    def delinquency(self) -> list[dict]:
        rows = self.repo.delinquency(self.clock.today())
        for row in rows:
            row["is_blocked"] = row["overdue_loans"] > 0 or policies.is_blocked_by_debt(
                row["pending_debt_cents"], self.settings.debt_block_threshold
            )
        return rows
