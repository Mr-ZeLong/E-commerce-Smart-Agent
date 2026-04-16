from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoutingRuleResponse(BaseModel):
    id: int
    intent_category: str
    target_agent: str
    priority: int
    condition_json: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentConfigResponse(BaseModel):
    id: int
    agent_name: str
    system_prompt: str | None = None
    previous_system_prompt: str | None = None
    confidence_threshold: float
    max_retries: int
    enabled: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentConfigListResponse(BaseModel):
    configs: list[AgentConfigResponse]
    routing_rules: list[RoutingRuleResponse]


class AgentConfigUpdateRequest(BaseModel):
    system_prompt: str | None = Field(default=None, max_length=10000)
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    enabled: bool | None = Field(default=None)


class AgentConfigUpdateResponse(BaseModel):
    success: bool
    agent_name: str
    message: str


class AgentConfigRollbackResponse(BaseModel):
    success: bool
    agent_name: str
    message: str


class RoutingRuleCreateRequest(BaseModel):
    intent_category: str = Field(..., max_length=32)
    target_agent: str = Field(..., max_length=32)
    priority: int = Field(..., ge=0, le=100)
    condition_json: dict | None = Field(default=None)


class RoutingRuleUpdateRequest(BaseModel):
    intent_category: str | None = Field(default=None, max_length=32)
    target_agent: str | None = Field(default=None, max_length=32)
    priority: int | None = Field(default=None, ge=0, le=100)
    condition_json: dict | None = Field(default=None)


class AgentConfigVersionResponse(BaseModel):
    id: int
    agent_name: str
    changed_by: int
    system_prompt: str | None = None
    confidence_threshold: float
    max_retries: int
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentConfigVersionMetricsResponse(BaseModel):
    total_sessions: int
    avg_confidence: float | None = None
    transfer_rate: float
    avg_latency_ms: float | None = None


class AgentConfigAuditLogResponse(BaseModel):
    id: int
    agent_name: str
    changed_by: int
    field_name: str
    old_value: str | None = None
    new_value: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptEffectReportResponse(BaseModel):
    id: int
    report_month: str
    agent_name: str
    version_id: int | None = None
    total_sessions: int
    avg_confidence: float | None = None
    transfer_rate: float
    avg_latency_ms: float | None = None
    key_changes: str | None = None
    recommendation: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FewShotEvalResponse(BaseModel):
    without_few_shot: dict
    with_few_shot: dict
    improvement: float
    meets_target: bool


class MultiIntentDecisionLogLabelRequest(BaseModel):
    human_label: bool = Field(description="人工标注结果")


class MultiIntentDecisionLogResponse(BaseModel):
    id: int
    query: str
    intent_a: str
    intent_b: str
    rule_based_result: bool | None = None
    llm_result: bool | None = None
    llm_reason: str | None = None
    human_label: bool | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
