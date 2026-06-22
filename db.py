from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import sessionmaker

from .const import RECURRENCE_CALENDAR
from .const import RECURRENCE_FROM_COMPLETION
from .const import RECURRENCE_ONE_OFF
from .const import UNIT_DAYS
from .const import UNIT_MONTHS
from .const import UNIT_WEEKS
from .table_models import Base
from .table_models import Chore
from .table_models import ChoreCompletion


class Database:
    def __init__(self, db_path: str):
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            future=True,
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
        )

    def create_tables(self):
        Base.metadata.create_all(self.engine)

    def list_chores(self) -> list[dict]:
        with self.SessionLocal() as session:
            chores = (
                session.query(Chore)
                .options(joinedload(Chore.completions))
                .order_by(Chore.next_due_at.asc().nullslast(), Chore.title.asc())
                .all()
            )
            return [self._serialize_chore(chore) for chore in chores]

    def list_due_chores(self, now_iso: str | None = None) -> list[dict]:
        now = self._parse_optional_iso(now_iso) or self._utcnow()
        with self.SessionLocal() as session:
            chores = (
                session.query(Chore)
                .filter(Chore.is_active.is_(True))
                .filter(Chore.is_done_once.is_(False))
                .filter(Chore.next_due_at.is_not(None))
                .filter(Chore.next_due_at <= now)
                .order_by(Chore.next_due_at.asc(), Chore.title.asc())
                .all()
            )
            return [self._serialize_chore(chore) for chore in chores]

    def create_chore(
        self,
        title: str,
        recurrence_mode: str,
        interval_value: int | None = None,
        interval_unit: str | None = None,
        calendar_weekday: int | None = None,
        calendar_day_of_month: int | None = None,
        anchor_date: str | None = None,
        first_due_at: str | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict:
        mode = self._validate_mode(recurrence_mode)
        value, unit = self._validate_interval(interval_value, interval_unit, mode)
        self._validate_calendar(mode, unit, calendar_weekday, calendar_day_of_month, anchor_date)

        now = self._utcnow()
        parsed_first_due = self._parse_optional_iso(first_due_at)
        use_due_time = self._should_use_due_time(first_due_at)

        chore = Chore(
            title=title,
            description=description,
            recurrence_mode=mode,
            interval_value=value,
            interval_unit=unit,
            calendar_weekday=calendar_weekday,
            calendar_day_of_month=calendar_day_of_month,
            anchor_date=anchor_date,
            next_due_at=self._compute_initial_due(
                mode=mode,
                value=value,
                unit=unit,
                weekday=calendar_weekday,
                day_of_month=calendar_day_of_month,
                anchor_date_str=anchor_date,
                now=now,
                first_due_at=parsed_first_due,
                use_due_time=use_due_time,
            ),
            last_completed_at=None,
            is_active=is_active,
            is_done_once=False,
            created_at=now,
        )

        with self.SessionLocal() as session:
            session.add(chore)
            session.commit()
            session.refresh(chore)
            return self._serialize_chore(chore)

    def update_chore(
        self,
        chore_id: int,
        title: str | None = None,
        description: str | None = None,
        recurrence_mode: str | None = None,
        interval_value: int | None = None,
        interval_unit: str | None = None,
        calendar_weekday: int | None = None,
        calendar_day_of_month: int | None = None,
        anchor_date: str | None = None,
        first_due_at: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        now = self._utcnow()

        with self.SessionLocal() as session:
            chore = session.query(Chore).filter(Chore.id == chore_id).one_or_none()
            if chore is None:
                raise ValueError(f"Chore with id {chore_id} does not exist")

            if title is not None:
                chore.title = title
            if description is not None:
                chore.description = description
            if is_active is not None:
                chore.is_active = is_active

            if recurrence_mode is not None:
                chore.recurrence_mode = recurrence_mode

            if interval_value is not None:
                chore.interval_value = interval_value
            if interval_unit is not None:
                chore.interval_unit = interval_unit

            if calendar_weekday is not None:
                chore.calendar_weekday = calendar_weekday
            if calendar_day_of_month is not None:
                chore.calendar_day_of_month = calendar_day_of_month
            if anchor_date is not None:
                chore.anchor_date = anchor_date

            mode = self._validate_mode(chore.recurrence_mode)
            value, unit = self._validate_interval(chore.interval_value, chore.interval_unit, mode)
            self._validate_calendar(
                mode,
                unit,
                chore.calendar_weekday,
                chore.calendar_day_of_month,
                chore.anchor_date,
            )

            chore.recurrence_mode = mode
            chore.interval_value = value
            chore.interval_unit = unit

            parsed_first_due = self._parse_optional_iso(first_due_at)
            should_use_due_time = self._should_use_due_time(first_due_at)
            if parsed_first_due is not None:
                chore.next_due_at = self._normalize_due_at(parsed_first_due, should_use_due_time)
            elif mode == RECURRENCE_ONE_OFF and chore.is_done_once:
                chore.next_due_at = None
            elif mode == RECURRENCE_CALENDAR:
                calendar_due = self._next_calendar_due(
                    value=value,
                    unit=unit,
                    weekday=chore.calendar_weekday,
                    day_of_month=chore.calendar_day_of_month,
                    anchor_date_str=chore.anchor_date,
                    reference_dt=self._normalize_due_at(now, self._has_time_component(chore.next_due_at)),
                )
                chore.next_due_at = self._normalize_due_at(calendar_due, self._has_time_component(chore.next_due_at))
            elif mode == RECURRENCE_FROM_COMPLETION and chore.last_completed_at:
                completion_due = self._add_interval(chore.last_completed_at, value, unit)
                chore.next_due_at = self._normalize_due_at(completion_due, self._has_time_component(chore.next_due_at))

            session.commit()
            session.refresh(chore)
            return self._serialize_chore(chore)

    def delete_chore(self, chore_id: int) -> dict:
        with self.SessionLocal() as session:
            chore = session.query(Chore).filter(Chore.id == chore_id).one_or_none()
            if chore is None:
                raise ValueError(f"Chore with id {chore_id} does not exist")
            session.delete(chore)
            session.commit()
            return {"id": chore_id}

    def mark_complete(self, chore_id: int, note: str | None = None) -> dict:
        now = self._utcnow()

        with self.SessionLocal() as session:
            chore = session.query(Chore).filter(Chore.id == chore_id).one_or_none()
            if chore is None:
                raise ValueError(f"Chore with id {chore_id} does not exist")
            if not chore.is_active:
                raise ValueError(f"Chore with id {chore_id} is not active")

            mode = self._validate_mode(chore.recurrence_mode)
            value, unit = self._validate_interval(chore.interval_value, chore.interval_unit, mode)

            completion = ChoreCompletion(
                chore_id=chore.id,
                completed_at=now,
                note=note,
                due_at_when_completed=chore.next_due_at,
            )

            if mode == RECURRENCE_ONE_OFF:
                chore.is_done_once = True
                chore.is_active = False
                chore.next_due_at = None
            elif mode == RECURRENCE_FROM_COMPLETION:
                next_due = self._add_interval(now, value, unit)
                chore.next_due_at = self._normalize_due_at(next_due, self._has_time_component(chore.next_due_at))
            else:
                # Calendar completion uses schedule alignment, but never before
                # completion plus one full interval.
                min_due_at = self._normalize_due_at(
                    self._add_interval(now, value, unit),
                    self._has_time_component(chore.next_due_at),
                )
                calendar_due = self._next_calendar_due(
                    value=value,
                    unit=unit,
                    weekday=chore.calendar_weekday,
                    day_of_month=chore.calendar_day_of_month,
                    anchor_date_str=chore.anchor_date,
                    reference_dt=min_due_at,
                    include_reference=True,
                )
                chore.next_due_at = self._normalize_due_at(calendar_due, self._has_time_component(chore.next_due_at))

            chore.last_completed_at = now
            completion.computed_next_due_at = chore.next_due_at

            session.add(completion)
            session.commit()
            session.refresh(chore)

            return {
                "completion": self._serialize_completion(completion),
                "chore": self._serialize_chore(chore),
            }

    def get_completion_history(self, chore_id: int, limit: int = 20) -> list[dict]:
        with self.SessionLocal() as session:
            completions = (
                session.query(ChoreCompletion)
                .filter(ChoreCompletion.chore_id == chore_id)
                .order_by(ChoreCompletion.completed_at.desc())
                .limit(limit)
                .all()
            )
            return [self._serialize_completion(item) for item in completions]

    def undo_last_completion(self, chore_id: int) -> dict:
        with self.SessionLocal() as session:
            chore = session.query(Chore).filter(Chore.id == chore_id).one_or_none()
            if chore is None:
                raise ValueError(f"Chore with id {chore_id} does not exist")

            last = (
                session.query(ChoreCompletion)
                .filter(ChoreCompletion.chore_id == chore_id)
                .order_by(ChoreCompletion.completed_at.desc())
                .first()
            )
            if last is None:
                raise ValueError(f"Chore with id {chore_id} has no completions to undo")

            # Restore the due date that was active before this completion.
            chore.next_due_at = last.due_at_when_completed

            # Restore last_completed_at from the previous completion, if any.
            previous = (
                session.query(ChoreCompletion)
                .filter(ChoreCompletion.chore_id == chore_id)
                .filter(ChoreCompletion.id != last.id)
                .order_by(ChoreCompletion.completed_at.desc())
                .first()
            )
            chore.last_completed_at = previous.completed_at if previous else None

            # For one_off chores, restore active state.
            if chore.recurrence_mode == RECURRENCE_ONE_OFF:
                chore.is_done_once = False
                chore.is_active = True

            session.delete(last)
            session.commit()
            session.refresh(chore)
            return self._serialize_chore(chore)

    def _validate_mode(self, mode: str | None) -> str:
        if mode not in {RECURRENCE_ONE_OFF, RECURRENCE_FROM_COMPLETION, RECURRENCE_CALENDAR}:
            raise ValueError(
                "recurrence_mode must be one of: one_off, from_completion, calendar"
            )
        return mode

    def _validate_interval(self, value: int | None, unit: str | None, mode: str) -> tuple[int | None, str | None]:
        if mode == RECURRENCE_ONE_OFF:
            return None, None

        if value is None:
            value = 1
        if value < 1:
            raise ValueError("interval_value must be >= 1")

        if unit is None:
            unit = UNIT_DAYS
        if unit not in {UNIT_DAYS, UNIT_WEEKS, UNIT_MONTHS}:
            raise ValueError("interval_unit must be one of: days, weeks, months")

        return value, unit

    def _validate_calendar(
        self,
        mode: str,
        unit: str | None,
        weekday: int | None,
        day_of_month: int | None,
        anchor_date_str: str | None,
    ) -> None:
        if mode != RECURRENCE_CALENDAR:
            return

        if unit == UNIT_WEEKS:
            if weekday is None or weekday < 0 or weekday > 6:
                raise ValueError("calendar weekly rules require calendar_weekday between 0 and 6")

        if unit == UNIT_MONTHS:
            if day_of_month is None or day_of_month < 1 or day_of_month > 31:
                raise ValueError("calendar monthly rules require calendar_day_of_month between 1 and 31")

        if unit == UNIT_DAYS:
            if anchor_date_str is not None:
                self._parse_anchor_date(anchor_date_str)

    def _compute_initial_due(
        self,
        mode: str,
        value: int | None,
        unit: str | None,
        weekday: int | None,
        day_of_month: int | None,
        anchor_date_str: str | None,
        now: datetime,
        first_due_at: datetime | None,
        use_due_time: bool,
    ) -> datetime | None:
        if first_due_at is not None:
            return self._normalize_due_at(first_due_at, use_due_time)

        if mode == RECURRENCE_ONE_OFF:
            return self._normalize_due_at(now, use_due_time)

        if mode == RECURRENCE_FROM_COMPLETION:
            return self._normalize_due_at(now, use_due_time)

        calendar_due = self._next_calendar_due(
            value=value,
            unit=unit,
            weekday=weekday,
            day_of_month=day_of_month,
            anchor_date_str=anchor_date_str,
            reference_dt=self._normalize_due_at(now, use_due_time),
        )
        return self._normalize_due_at(calendar_due, use_due_time)

    def _next_calendar_due(
        self,
        value: int | None,
        unit: str | None,
        weekday: int | None,
        day_of_month: int | None,
        anchor_date_str: str | None,
        reference_dt: datetime,
        include_reference: bool = False,
    ) -> datetime:
        if value is None or unit is None:
            raise ValueError("Calendar recurrence requires interval_value and interval_unit")

        def _is_before_threshold(candidate: datetime) -> bool:
            if include_reference:
                return candidate < reference_dt
            return candidate <= reference_dt

        # Always return a future due occurrence for fixed schedules.
        if unit == UNIT_DAYS:
            anchor = self._parse_anchor_date(anchor_date_str) if anchor_date_str else reference_dt.date()
            due_date = datetime.combine(anchor, time.min, tzinfo=timezone.utc)
            while _is_before_threshold(due_date):
                due_date += timedelta(days=value)
            return due_date

        if unit == UNIT_WEEKS:
            if weekday is None:
                raise ValueError("calendar_weekday is required for weekly calendar chores")

            anchor = self._parse_anchor_date(anchor_date_str) if anchor_date_str else reference_dt.date()
            due_date = self._first_weekday_on_or_after(anchor, weekday)
            due_dt = datetime.combine(due_date, time.min, tzinfo=timezone.utc)
            while _is_before_threshold(due_dt):
                due_dt += timedelta(weeks=value)
            return due_dt

        if unit == UNIT_MONTHS:
            if day_of_month is None:
                raise ValueError("calendar_day_of_month is required for monthly calendar chores")

            anchor = self._parse_anchor_date(anchor_date_str) if anchor_date_str else reference_dt.date()
            due_dt = datetime.combine(
                self._clamp_day_in_month(anchor.year, anchor.month, day_of_month),
                time.min,
                tzinfo=timezone.utc,
            )
            while _is_before_threshold(due_dt):
                due_dt = due_dt + relativedelta(months=value)
                due_dt = due_dt.replace(
                    day=self._clamp_day_in_month(due_dt.year, due_dt.month, day_of_month).day
                )
            return due_dt

        raise ValueError("Unsupported calendar interval unit")

    def _add_interval(self, base_dt: datetime, interval_value: int | None, interval_unit: str | None) -> datetime:
        if interval_value is None or interval_unit is None:
            raise ValueError("interval_value and interval_unit are required")

        if interval_unit == UNIT_DAYS:
            return base_dt + timedelta(days=interval_value)
        if interval_unit == UNIT_WEEKS:
            return base_dt + timedelta(weeks=interval_value)
        if interval_unit == UNIT_MONTHS:
            return base_dt + relativedelta(months=interval_value)

        raise ValueError("interval_unit must be one of: days, weeks, months")

    def _serialize_chore(self, chore: Chore) -> dict:
        return {
            "id": chore.id,
            "title": chore.title,
            "description": chore.description,
            "recurrence_mode": chore.recurrence_mode,
            "interval_value": chore.interval_value,
            "interval_unit": chore.interval_unit,
            "calendar_weekday": chore.calendar_weekday,
            "calendar_day_of_month": chore.calendar_day_of_month,
            "anchor_date": chore.anchor_date,
            "next_due_at": self._iso_or_none(chore.next_due_at),
            "last_completed_at": self._iso_or_none(chore.last_completed_at),
            "is_active": bool(chore.is_active),
            "is_done_once": bool(chore.is_done_once),
            "created_at": self._iso_or_none(chore.created_at),
        }

    def _serialize_completion(self, completion: ChoreCompletion) -> dict:
        return {
            "id": completion.id,
            "chore_id": completion.chore_id,
            "completed_at": self._iso_or_none(completion.completed_at),
            "note": completion.note,
            "due_at_when_completed": self._iso_or_none(completion.due_at_when_completed),
            "computed_next_due_at": self._iso_or_none(completion.computed_next_due_at),
        }

    def _iso_or_none(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def _parse_optional_iso(self, value: str | None) -> datetime | None:
        if value in (None, ""):
            return None
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return self._as_utc(dt)

    def _should_use_due_time(self, iso_value: str | None) -> bool:
        if not iso_value:
            return False
        normalized = iso_value.strip().replace("Z", "+00:00")
        return "T" in normalized

    def _parse_anchor_date(self, anchor_date_str: str) -> date:
        return date.fromisoformat(anchor_date_str)

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _as_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _has_time_component(self, dt: datetime | None) -> bool:
        if dt is None:
            return False
        dt_utc = self._as_utc(dt)
        return not (
            dt_utc.hour == 0
            and dt_utc.minute == 0
            and dt_utc.second == 0
            and dt_utc.microsecond == 0
        )

    def _normalize_due_at(self, due_at: datetime, use_due_time: bool) -> datetime:
        due_at_utc = self._as_utc(due_at)
        if use_due_time:
            return due_at_utc
        return datetime.combine(due_at_utc.date(), time.min, tzinfo=timezone.utc)

    def _first_weekday_on_or_after(self, anchor: date, target_weekday: int) -> date:
        delta = (target_weekday - anchor.weekday()) % 7
        return anchor + timedelta(days=delta)

    def _clamp_day_in_month(self, year: int, month: int, day_of_month: int) -> date:
        first_of_month = date(year, month, 1)
        next_month = first_of_month + relativedelta(months=1)
        last_day = (next_month - timedelta(days=1)).day
        return date(year, month, min(day_of_month, last_day))
