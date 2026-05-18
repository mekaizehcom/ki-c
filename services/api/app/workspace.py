"""Workspace loader + steering-file parsers (OpenClaw-style).

Reads /workspaces/<slug>/{SOUL,AGENTS,TOOLS,POLICIES,MODELS,ROUTING,
VECTOR,APPROVALS}.md + config/workspace.yaml + skills/, parses them into
in-memory structures, caches them, and upserts agents/model_profiles into
Postgres so the admin panel (Phase 6) can manage them.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Agent, ModelProfile, Workspace


@dataclass
class AgentDef:
    name: str
    purpose: str = ""
    model_profile: str = "default-balanced"
    tools: list[str] = field(default_factory=list)
    autonomy: str = "approve_required"
    approval_actions: list[str] = field(default_factory=list)


@dataclass
class ModelProfileDef:
    name: str
    purpose: str = ""
    providers: list[str] = field(default_factory=list)  # e.g. "openai/gpt-4.1"


@dataclass
class WorkspaceDef:
    slug: str
    name: str
    soul: str
    agents: dict[str, AgentDef]
    model_profiles: dict[str, ModelProfileDef]
    routing_text: str
    policies_text: str
    approvals_text: str
    skills: dict[str, str]
    config: dict


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def _split_sections(md: str) -> dict[str, str]:
    """Split markdown on '## heading' into {heading: body}."""
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


def _labeled(body: str) -> dict[str, list[str]]:
    """Parse 'Label:' blocks; value is following non-empty lines/bullets."""
    out: dict[str, list[str]] = {}
    label = None
    for raw in body.splitlines():
        line = raw.strip()
        m = re.match(r"^([A-Za-zÄÖÜäöü ]+):\s*(.*)$", line)
        if m and not line.startswith("-"):
            label = m.group(1).strip().lower()
            rest = m.group(2).strip()
            out[label] = [rest] if rest else []
        elif line.startswith("- ") and label:
            out[label].append(line[2:].strip())
        elif line and label and not out[label]:
            out[label] = [line]
    return out


def _parse_agents(md: str) -> dict[str, AgentDef]:
    agents: dict[str, AgentDef] = {}
    for name, body in _split_sections(md).items():
        lb = _labeled(body)
        agents[name] = AgentDef(
            name=name,
            purpose=" ".join(lb.get("zweck", [])).strip(),
            model_profile=(lb.get("modellprofil", ["default-balanced"]) or
                           ["default-balanced"])[0].strip() or "default-balanced",
            tools=[t for t in lb.get("tools", []) if t],
            autonomy=(lb.get("autonomie", ["approve_required"]) or
                      ["approve_required"])[0].strip() or "approve_required",
            approval_actions=lb.get("approval erforderlich für", []),
        )
    return agents


def _parse_model_profiles(md: str) -> dict[str, ModelProfileDef]:
    profiles: dict[str, ModelProfileDef] = {}
    for name, body in _split_sections(md).items():
        lb = _labeled(body)
        profiles[name] = ModelProfileDef(
            name=name,
            purpose=" ".join(lb.get("zweck", [])).strip(),
            providers=[p for p in lb.get("provider", []) if p],
        )
    return profiles


def _load_skills(skills_dir: str) -> dict[str, str]:
    skills: dict[str, str] = {}
    if not os.path.isdir(skills_dir):
        return skills
    for entry in sorted(os.listdir(skills_dir)):
        sp = os.path.join(skills_dir, entry, "SKILL.md")
        if os.path.isfile(sp):
            skills[entry] = _read(sp)
    return skills


@lru_cache(maxsize=8)
def load_workspace(slug: str) -> WorkspaceDef:
    base = os.path.join(settings.tessa_workspaces_dir, slug)
    cfg_raw = _read(os.path.join(base, "config", "workspace.yaml"))
    cfg = yaml.safe_load(cfg_raw) if cfg_raw else {}
    return WorkspaceDef(
        slug=slug,
        name=(cfg or {}).get("name", slug),
        soul=_read(os.path.join(base, "SOUL.md")),
        agents=_parse_agents(_read(os.path.join(base, "AGENTS.md"))),
        model_profiles=_parse_model_profiles(_read(os.path.join(base, "MODELS.md"))),
        routing_text=_read(os.path.join(base, "ROUTING.md")),
        policies_text=_read(os.path.join(base, "POLICIES.md")),
        approvals_text=_read(os.path.join(base, "APPROVALS.md")),
        skills=_load_skills(os.path.join(base, "skills")),
        config=cfg or {},
    )


def clear_cache() -> None:
    load_workspace.cache_clear()


def sync_to_db(db: Session, ws: WorkspaceDef) -> None:
    """Upsert workspace, agents and model profiles into Postgres."""
    row = db.scalar(select(Workspace).where(Workspace.slug == ws.slug))
    if not row:
        row = Workspace(slug=ws.slug, name=ws.name, config=ws.config)
        db.add(row)
        db.flush()
    else:
        row.name = ws.name
        row.config = ws.config

    for name, prof in ws.model_profiles.items():
        mp = db.get(ModelProfile, name)
        if not mp:
            db.add(ModelProfile(name=name, purpose=prof.purpose,
                                providers=prof.providers))
        else:
            mp.purpose, mp.providers = prof.purpose, prof.providers

    for name, a in ws.agents.items():
        ag = db.scalar(
            select(Agent).where(Agent.workspace_id == row.id, Agent.name == name)
        )
        if not ag:
            db.add(Agent(
                workspace_id=row.id, name=name, purpose=a.purpose,
                model_profile=a.model_profile, tools=a.tools,
                autonomy=a.autonomy, approval_actions=a.approval_actions,
            ))
        else:
            ag.purpose = a.purpose
            ag.model_profile = a.model_profile
            ag.tools = a.tools
            ag.autonomy = a.autonomy
            ag.approval_actions = a.approval_actions
    db.commit()
