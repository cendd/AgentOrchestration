"""Workflow definitions with input validation."""

import json
import logging
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class WorkflowValidationError(ValueError):
    """Raised when workflow validation fails."""


@dataclass
class WorkflowStep:
    id: str = ""
    name: str = ""
    agent: str = ""
    input: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    timeout: int = 300


class Workflow:
    def __init__(self, name: str, steps: Optional[List[WorkflowStep]] = None):
        self.id = str(uuid4())
        self.name = name
        self.steps = steps or []
        self._validate()

    def _validate(self) -> None:
        """Validate workflow structure and reject duplicate parameter aliases."""
        seen_aliases: Set[str] = set()
        seen_step_names: Set[str] = set()
        errors: List[str] = []

        for step in self.steps:
            # Check duplicate step names
            if step.name in seen_step_names:
                errors.append(f"Duplicate step name: '{step.name}'")
            seen_step_names.add(step.name)

            # Check duplicate parameter aliases in input
            for key in step.input:
                lower_key = key.lower().replace("_", "").replace("-", "")
                if lower_key in seen_aliases:
                    errors.append(
                        f"Duplicate parameter alias: '{key}' collides with existing alias "
                        f"(normalized: '{lower_key}') in step '{step.name}'"
                    )
                seen_aliases.add(lower_key)

        if errors:
            raise WorkflowValidationError("; ".join(errors))

    def add_step(self, step: WorkflowStep) -> None:
        self.steps.append(step)
        # Re-validate after adding
        try:
            self._validate()
        except WorkflowValidationError:
            self.steps.pop()
            raise

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "steps": [
                {
                    "id": s.id or str(uuid4()),
                    "name": s.name,
                    "agent": s.agent,
                    "input": s.input,
                    "depends_on": s.depends_on,
                    "timeout": s.timeout,
                }
                for s in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Workflow":
        steps = [WorkflowStep(**s) for s in data.get("steps", [])]
        return cls(name=data["name"], steps=steps)
