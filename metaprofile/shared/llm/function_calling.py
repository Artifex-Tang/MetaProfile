"""
LLM Function Calling 调用器。

所有 Schema-Guided IE 调用必须通过此模块，禁止用纯文本 prompt 解析。
"""
from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from metaprofile.shared.llm.gateway import LLMGateway, LLMGatewayError, LLMResponse

T = TypeVar("T", bound=BaseModel)


class FunctionCallingMismatch(LLMGatewayError):
    """LLM 没有按预期调用 function 或返回 schema 不匹配。"""


async def call_with_schema(
    *,
    gateway: LLMGateway,
    model: str,
    system_prompt: str,
    user_prompt: str,
    function_name: str,
    function_description: str,
    output_schema: type[T],
    caller: str,
) -> tuple[T, LLMResponse]:
    """
    用 Pydantic 模型作为 schema 约束 LLM 输出。

    Args:
        output_schema: Pydantic 模型类，model_json_schema() 转为 OpenAI function 定义
        caller: 调用方标识

    Returns:
        (parsed_pydantic_instance, raw_llm_response)

    Raises:
        FunctionCallingMismatch: LLM 没调用 function 或参数解析失败
    """
    json_schema = output_schema.model_json_schema()
    function_def = {
        "name": function_name,
        "description": function_description,
        "parameters": json_schema,
    }

    response = await gateway.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        functions=[function_def],
        function_call={"name": function_name},
        caller=caller,
    )

    if not response.function_call:
        raise FunctionCallingMismatch(
            f"LLM did not call function {function_name!r}; raw content: {response.content!r}"
        )

    raw_args = response.function_call.get("arguments", "")
    try:
        parsed_dict = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError as e:
        raise FunctionCallingMismatch(
            f"function_call.arguments is not valid JSON: {e}; raw: {raw_args!r}"
        ) from e

    try:
        instance = output_schema.model_validate(parsed_dict)
    except ValidationError as e:
        raise FunctionCallingMismatch(
            f"function_call.arguments does not match schema: {e}"
        ) from e

    return instance, response


def schema_to_function_def(
    schema: type[BaseModel], name: str, description: str
) -> dict[str, Any]:
    """工具函数：把 Pydantic 模型转为 OpenAI function 定义。"""
    return {
        "name": name,
        "description": description,
        "parameters": schema.model_json_schema(),
    }
