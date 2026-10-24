"""
Pydantic Schemas for AI Stewardship Structured Outputs and Guardrail Validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class StandardizeLocationOutput(BaseModel):
    standardized_city: str = Field(..., description="Canonical title-cased city name")
    standardized_state: str = Field(..., description="Full state name")
    country: str = Field(..., description="2-letter ISO country code")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reason: str = Field(..., description="Remediation rationale")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be strictly between 0.0 and 1.0")
        return round(float(v), 4)

class RoleClassificationOutput(BaseModel):
    category: str = Field(..., description="Department: Engineering, Sales, Finance, Operations, Marketing, Healthcare, Executive, Other")
    seniority: str = Field(..., description="Seniority level: Entry, Mid, Senior, Director, VP, C-Suite, Unknown")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., description="Classification justification")

class IssueExplanationOutput(BaseModel):
    violation_summary: str = Field(..., description="Plain-English explanation of the defect")
    root_cause: str = Field(..., description="Probable upstream cause")
    suggested_action: str = Field(..., description="Specific recommended fix for steward")
    auto_fixable: bool = Field(..., description="Whether this can be safely automated")
    confidence: float = Field(..., ge=0.0, le=1.0)

class IncidentRecommendationOutput(BaseModel):
    incident_id: str = Field(..., description="Target incident ID")
    title: str = Field(..., description="Concise diagnostic title")
    recommended_fix: str = Field(..., description="Actionable fix instructions")
    cited_incident_ids: List[str] = Field(default_factory=list, description="Historical incident citations")
    suggested_runbook_action: str = Field(..., description="Automated runbook action to trigger")
    risk_level: str = Field(..., description="Low, Medium, or High")
    can_auto_execute: bool = Field(..., description="True only if low risk and high certainty")
