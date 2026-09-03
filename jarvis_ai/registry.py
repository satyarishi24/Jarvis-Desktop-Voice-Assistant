"""The tool registry: how a Python function becomes something Claude can call."""

from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .permissions import Approver, Denied, Risk

_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


class ToolError(Exception):
    """A tool failed in a way Claude should see and be able to react to."""


def _schema_for(annotation: Any) -> Dict[str, Any]:
    """Translate a type hint into the JSON Schema fragment for one parameter."""
    origin = typing.get_origin(annotation)

    if origin is list or annotation is list:
        (item,) = typing.get_args(annotation) or (str,)
        return {"type": "array", "items": _schema_for(item)}

    if origin is typing.Union:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _schema_for(args[0])
        return {}  # genuinely mixed — let the model send whatever fits

    if annotation in _JSON_TYPES:
        return {"type": _JSON_TYPES[annotation]}

    return {"type": "string"}


@dataclass
class Tool:
    """One capability, with the metadata the approval gate needs."""

    name: str
    description: str
    risk: Risk
    func: Callable[..., str]
    schema: Dict[str, Any]
    preview: Callable[..., str]

    def spec(self) -> Dict[str, Any]:
        """The tool definition sent to the Messages API."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.schema,
        }

    def describe(self, args: Dict[str, Any]) -> str:
        """One line explaining what this call would do, shown before approving."""
        try:
            return self.preview(**args)
        except Exception:  # a broken preview must never block the call
            return f"{self.name}({', '.join(f'{k}={v!r}' for k, v in args.items())})"


@dataclass
class Registry:
    """Holds every tool and dispatches calls through the approver."""

    tools: Dict[str, Tool] = field(default_factory=dict)

    def add(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self.tools[tool.name] = tool

    def specs(self) -> List[Dict[str, Any]]:
        return [tool.spec() for tool in sorted(self.tools.values(), key=lambda t: t.name)]

    def call(self, name: str, args: Dict[str, Any], ctx: "ToolContext") -> str:
        """Run a tool by name. Raises :class:`Denied` or :class:`ToolError`."""
        tool = self.tools.get(name)
        if tool is None:
            raise ToolError(f"No such tool: {name}")

        unknown = set(args) - set(tool.schema["properties"])
        if unknown:
            raise ToolError(
                f"{name} has no parameter(s) named {', '.join(sorted(unknown))}. "
                f"Valid parameters: {', '.join(sorted(tool.schema['properties']))}."
            )
        missing = set(tool.schema["required"]) - set(args)
        if missing:
            raise ToolError(f"{name} is missing required argument(s): {', '.join(sorted(missing))}.")

        description = tool.describe(args)
        ctx.approver.check(name, description, tool.risk)

        if ctx.approver.dry_run and tool.risk is not Risk.READ:
            return f"[dry run] Would have done: {description}"

        return tool.func(ctx, **args)


#: The single registry every tool module registers into at import time.
REGISTRY = Registry()


def tool(
    *,
    risk: Risk,
    description: str,
    params: Optional[Dict[str, str]] = None,
    preview: Optional[Callable[..., str]] = None,
    name: Optional[str] = None,
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Register a function as a Claude tool.

    The JSON schema is derived from the signature: every parameter after ``ctx``
    becomes a property, typed from its annotation and documented by ``params``.
    Parameters without a default are required.
    """

    def decorator(func: Callable[..., str]) -> Callable[..., str]:
        signature = inspect.signature(func)
        hints = typing.get_type_hints(func)
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param_name, param in signature.parameters.items():
            if param_name == "ctx":
                continue
            entry = _schema_for(hints.get(param_name, str))
            doc = (params or {}).get(param_name)
            if doc:
                entry["description"] = doc
            properties[param_name] = entry
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        REGISTRY.add(
            Tool(
                name=name or func.__name__,
                description=description,
                risk=risk,
                func=func,
                schema={
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
                preview=preview or (lambda **kw: description),
            )
        )
        return func

    return decorator


@dataclass
class ToolContext:
    """Everything a tool needs that isn't one of its own arguments."""

    settings: Any
    approver: Approver
    speak: Callable[[str], None] = lambda text: None
    notify: Callable[[str], None] = lambda text: None
