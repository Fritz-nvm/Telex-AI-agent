from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class MessagePart(BaseModel):
    kind: Literal["text", "data"]
    text: Optional[str] = None
    data: Optional[List[Any]] = None


class TelexMessage(BaseModel):
    kind: Literal["message"]
    role: Literal["user", "agent"]
    parts: List[MessagePart]
    messageId: str
    taskId: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskStatus(BaseModel):
    state: Literal["completed", "failed", "running", "pending"]
    timestamp: str
    message: Optional[TelexMessage] = None


class TaskResult(BaseModel):
    id: str
    contextId: str
    status: TaskStatus
    artifacts: List[Any] = []
    history: List[TelexMessage] = []
    kind: Literal["task"]


class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"]
    method: str
    params: Dict[str, Any]
    id: str


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"]
    id: str
    result: Optional[TaskResult] = None
    error: Optional[Dict[str, Any]] = None


class PushNotificationConfig(BaseModel):
    url: str
    token: str
    authentication: Dict[str, List[str]]


class Configuration(BaseModel):
    acceptedOutputModes: List[str] = []
    historyLength: int = 0
    blocking: bool = True
    pushNotificationConfig: Optional[PushNotificationConfig] = None
