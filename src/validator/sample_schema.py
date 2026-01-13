#!/usr/bin/env python
# coding: utf-8

from typing import List, Literal
from pydantic import BaseModel, Field

SourceType = Literal["doc", "code", "config"]
TaskType = Literal["qa", "design"]
BusinessStage = Literal["exposure", "hazard", "gul", "fm", "aggregation", "other"]
Difficulty = Literal["easy", "medium", "hard"]
Language = Literal["zh", "en"]

class ContextItem(BaseModel):
    source_type: SourceType
    path: str
    content: str

class TraceStep(BaseModel):
    step: int = Field(ge=1)
    goal: str
    evidence_ref: List[str]
    intermediate_conclusion: str

class Metadata(BaseModel):
    repo: str
    business_stage: BusinessStage
    question_id: str
    difficulty: Difficulty
    language: Language

class TrainingSample(BaseModel):
    id: str
    task_type: TaskType
    instruction: str
    context: List[ContextItem]
    reasoning_trace: List[TraceStep]
    output: str
    metadata: Metadata
