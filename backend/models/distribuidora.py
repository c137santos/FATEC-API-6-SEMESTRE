from datetime import date, datetime

from sqlalchemy import Date, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

try:
    from core.models import table_registry
except ModuleNotFoundError:  # pragma: no cover
    from backend.core.models import table_registry


@table_registry.mapped_as_dataclass
class Distribuidora:
    __tablename__ = 'distribuidoras'

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    data_gdb: Mapped[date] = mapped_column(Date, primary_key=True)
    nome_distribuidora: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
        type_=DateTime(timezone=False),
    )