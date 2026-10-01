from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Message(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(StrictModel):
    messages: list[Message] = Field(min_length=1, max_length=40)
    stream: bool = True

    @model_validator(mode="after")
    def validate_history(self):
        if self.messages[-1].role != "user":
            raise ValueError("Last message must be from the user")
        if sum(len(m.content) for m in self.messages) > 40000:
            raise ValueError("Conversation too long; start a new conversation")
        return self


class ImageRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=4000)
    size: Literal["512x512", "768x768", "1024x1024", "1024x1536", "1536x1024"] = "1024x1024"


class LoginRequest(StrictModel):
    access_code: str = Field(default="", max_length=256)
