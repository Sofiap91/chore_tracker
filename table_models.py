from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Chore(Base):
    __tablename__ = "chores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    recurrence_mode = Column(String, nullable=False)
    interval_value = Column(Integer, nullable=True)
    interval_unit = Column(String, nullable=True)

    # Calendar mode options.
    calendar_weekday = Column(Integer, nullable=True)  # 0=Mon..6=Sun
    calendar_day_of_month = Column(Integer, nullable=True)  # 1..31
    anchor_date = Column(String, nullable=True)  # YYYY-MM-DD for daily cadence anchors

    next_due_at = Column(DateTime(timezone=True), nullable=True)
    last_completed_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    is_done_once = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    completions = relationship(
        "ChoreCompletion",
        back_populates="chore",
        cascade="all, delete-orphan",
    )


class ChoreCompletion(Base):
    __tablename__ = "chore_completions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chore_id = Column(Integer, ForeignKey("chores.id"), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    note = Column(Text, nullable=True)
    due_at_when_completed = Column(DateTime(timezone=True), nullable=True)
    computed_next_due_at = Column(DateTime(timezone=True), nullable=True)

    chore = relationship("Chore", back_populates="completions")
