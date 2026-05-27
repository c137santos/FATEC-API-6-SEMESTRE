from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, HttpUrl


class Message(BaseModel):
    message: str


class ConsentPolicyPublic(BaseModel):
    id: int
    version: str
    content: str
    is_mandatory: bool
    model_config = ConfigDict(from_attributes=True)


class ConsentPoliciesPublic(BaseModel):
    mandatory: ConsentPolicyPublic
    optional: ConsentPolicyPublic | None = None


class UserConsentPublic(BaseModel):
    consent_policy_id: int
    policy_version: str
    policy_content: str
    is_mandatory: bool
    accepted: bool
    consented_at: datetime


class UserSchema(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserCreateSchema(UserSchema):
    consented: bool
    optional_consented: bool = False


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    consented_at: datetime | None = None
    consent_policy_id: int | None = None
    model_config = ConfigDict(from_attributes=True)


class UserList(BaseModel):
    users: list[UserPublic]


class Token(BaseModel):
    access_token: str
    token_type: str


class ResendVerificationSchema(BaseModel):
    email: EmailStr


class CriticidadeResponse(BaseModel):
    ano: int
    distribuidora: str
    score_criticidade: float
    desvio_dec: float
    desvio_fec: float
    cor: str


class DistribuidoraPayload(BaseModel):
    id: str | None
    dist_name: str
    date_gdb: int | None


class SyncDistribuidorasResponse(BaseModel):
    total_recebidas: int
    total_persistidas: int
    enrichment_task_id: str


class DownloadRequest(BaseModel):
    url: HttpUrl


class DecFecRequest(BaseModel):
    url_realizado: HttpUrl
    url_limite: HttpUrl


class PipelineTriggerRequest(BaseModel):
    distribuidora_id: str
    ano: int


class PipelineTriggerResponse(BaseModel):
    status: str
    job_id: str
    task_id: str
    distribuidora_id: str
    ano: int
    download_url: str


class DistributorResponse(BaseModel):
    id: str
    nome: str
    ano: int


class DistributorMetadata(BaseModel):
    id: str
    date_gdb: int
    dist_name: str
    job_id: str


class ReportStatusResponse(BaseModel):
    job_id: str
    etl_status: str
    report_status: str
    report_pdf_path: str | None


class TamRequest(BaseModel):
    job_id: str


class TamResponse(BaseModel):
    job_id: str
    id_dist: str
    dist_name: str
    ano_gdb: int
    data_processamento: str
    CONJ: str
    CTMT: str
    NOME: str | None
    COMP_KM: float
    model_config = ConfigDict(from_attributes=True)


class CnpjLookupResponse(BaseModel):
    dist_id: str
    dist_name: str
    cnpj_enrichment_status: str | None
    message: str


class OAuthClientCreate(BaseModel):
    client_name: str
    redirect_uris: list[str]
    allowed_scopes: list[str]


class OAuthClientCreatedResponse(BaseModel):
    client_id: str
