"""抽取器抽象基类。所有 LLM Function Calling 抽取器统一接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from metaprofile.shared.llm.gateway import LLMGateway

T = TypeVar("T", bound=BaseModel)


class AbstractExtractor(ABC, Generic[T]):
    """属性抽取器抽象基类。

    每个实体类型实现一个具体抽取器：
        TechExtractor / OrgExtractor / ProjectExtractor / PersonExtractor
    """

    caller_name: str  # 子类必须设置（用于 token_meter caller 标识）

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    @abstractmethod
    async def extract(self, text: str, *, source_doc_id: str | None = None) -> T:
        """从文本中抽取实体属性。

        Args:
            text: 实体上下文（NER 实体 span ± 500 字）
            source_doc_id: 源文档 ID，用于审计追溯

        Returns:
            Pydantic 实例（数据规范字段）

        Raises:
            FunctionCallingMismatch: LLM 输出不符合 schema
        """
