"""Pydantic models for OSWorld task configuration."""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field


class Action(BaseModel):
    """Represents a single action in task configuration."""
    type: str = Field(..., description="Action type (launch, sleep, chrome_open_tabs, etc.)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")


class Evaluator(BaseModel):
    """Represents task evaluation configuration."""
    postconfig: List[Action] = Field(default_factory=list, description="Post-execution configuration")
    func: Any = Field(..., description="Evaluation function name (string or list)")
    result: Any = Field(default_factory=dict, description="Result configuration (dict or list)")
    expected: Any = Field(default_factory=dict, description="Expected result (dict or list)")
    
    @property
    def func_name(self) -> str:
        """Get the primary function name."""
        if isinstance(self.func, list):
            return self.func[0] if self.func else "unknown"
        return str(self.func)


class Task(BaseModel):
    """Represents a complete OSWorld task."""
    id: str = Field(..., description="Unique task identifier")
    snapshot: Optional[str] = Field(None, description="VM snapshot name")
    instruction: str = Field(..., description="Human-readable task instruction")
    source: Optional[str] = Field(None, description="Source URL or reference")
    config: List[Action] = Field(default_factory=list, description="Task configuration actions")
    trajectory: Optional[str] = Field(None, description="Trajectory path")
    related_apps: List[str] = Field(default_factory=list, description="Related applications")
    evaluator: Optional[Evaluator] = Field(None, description="Task evaluator")
    proxy: bool = Field(False, description="Whether proxy is required")
    fixed_ip: bool = Field(False, description="Whether fixed IP is required")
    possibility_of_env_change: str = Field("low", description="Environment change possibility")

    @classmethod
    def parse_file(cls, path: str) -> "Task":
        """Parse task from JSON file."""
        import json
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)
