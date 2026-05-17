import time

from authlib.integrations.sqla_oauth2 import (
    OAuth2AuthorizationCodeMixin,
    OAuth2ClientMixin,
    OAuth2TokenMixin,
)
from sqlalchemy import Column, ForeignKey, Integer

from backend.core.models import table_registry

_Base = table_registry.generate_base()


class OAuth2Client(_Base, OAuth2ClientMixin):
    __tablename__ = 'oauth2_clients'

    id = Column(Integer, primary_key=True, autoincrement=True)


class OAuth2AuthorizationCode(_Base, OAuth2AuthorizationCodeMixin):
    __tablename__ = 'oauth2_authorization_codes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )

    def is_expired(self):
        return self.auth_time + 60 < time.time()


class OAuth2Token(_Base, OAuth2TokenMixin):
    __tablename__ = 'oauth2_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
