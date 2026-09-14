"""Tool permission contracts. Agents only receive tools they are granted."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    required_permission: str


class ToolGrant(BaseModel):
    agent_id: str
    tools: list[str] = Field(default_factory=list)


CATALOG: tuple[ToolSpec, ...] = (
    ToolSpec(name="web_search", description="Search the public web", required_permission="use_web_search"),
    ToolSpec(name="python", description="Run sandboxed Python", required_permission="use_python"),
    ToolSpec(name="company_memory", description="Read/write company memory", required_permission="read_company_knowledge"),
    ToolSpec(name="filesystem", description="Company file store", required_permission="use_filesystem"),
    ToolSpec(name="github", description="GitHub operations", required_permission="use_github"),
    ToolSpec(name="database", description="Approved database queries", required_permission="use_database"),
    ToolSpec(name="browser", description="Headless browser", required_permission="use_browser"),
    ToolSpec(name="custom_api", description="Company-configured HTTP tools", required_permission="use_custom_api"),
)


def tools_for_permissions(permissions: set[str]) -> list[ToolSpec]:
    return [spec for spec in CATALOG if spec.required_permission in permissions]
