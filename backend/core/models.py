from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, registry

table_registry = registry()


@table_registry.mapped_as_dataclass
class ConsentPolicy:
    __tablename__ = 'consent_policies'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    version: Mapped[str] = mapped_column(Text, unique=True)
    content: Mapped[str] = mapped_column(Text)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )


@table_registry.mapped_as_dataclass
class UserConsent:
    __tablename__ = 'user_consents'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE')
    )
    consent_policy_id: Mapped[int] = mapped_column(
        ForeignKey('consent_policies.id')
    )
    accepted: Mapped[bool] = mapped_column(Boolean)
    consented_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )


@table_registry.mapped_as_dataclass
class User:
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
    consent_policy_id: Mapped[int | None] = mapped_column(
        ForeignKey('consent_policies.id'), nullable=True, default=None
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_token: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    email_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )


@table_registry.mapped_as_dataclass
class Distribuidora:
    __tablename__ = 'distribuidoras'

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    date_gdb: Mapped[int] = mapped_column(Integer, primary_key=True)
    dist_name: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        default=None,
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
        type_=DateTime(timezone=False),
    )


@table_registry.mapped_as_dataclass
class DistribuidoraCnpj:
    __tablename__ = 'distribuidora_cnpj'

    dist_id: Mapped[str] = mapped_column(Text, primary_key=True)
    cnpj: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    cnpj_match: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
    )
    cnpj_source: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    cnpj_enrichment_status: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False,
        server_default=func.now(),
        onupdate=func.now(),
        type_=DateTime(timezone=False),
    )
