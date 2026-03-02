from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    system_prompt: str
    provider: str
    model: str
    token_limit: int = Field(gt=100)
    tools: dict = Field(default_factory=dict)
    memory_enabled: bool = False
    behavior: dict = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    text: str


class AgentResponse(BaseModel):
    answer: str
    spent_tokens: int
