"""Validated inputs for formulation comparisons and laboratory observations."""

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .auth import StrictModel

CRITERIA = ("oxidation", "solubility", "compatibility", "temperature", "aroma")


class Ingredient(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    role: Literal["active", "fragrance", "solubilizer", "stabilizer", "solvent", "water", "other"]
    percent: float = Field(gt=0, le=100)
    smiles: str = Field(default="", max_length=2000)


class FormulationInput(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    aroma_profile: str = Field(default="", max_length=240)
    ingredients: list[Ingredient] = Field(min_length=1, max_length=30)
    notes: str = Field(default="", max_length=1500)
    data_origin: Literal["real", "synthetic"] = "real"

    @model_validator(mode="after")
    def total(self):
        if abs(sum(x.percent for x in self.ingredients) - 100) > 0.01:
            raise ValueError("Total komposisi wajib 100% massa.")
        return self

    def fingerprint(self) -> str:
        entries = sorted(
            (x.name.lower(), x.role, round(x.percent, 6), x.smiles) for x in self.ingredients
        )
        return hashlib.sha256(json.dumps(entries).encode()).hexdigest()


class Criterion(StrictModel):
    score: float = Field(ge=0, le=100)
    source_ref: str = Field(min_length=3, max_length=240)
    rationale: str = Field(min_length=3, max_length=800)


class Assessment(StrictModel):
    oxidation: Criterion | None = None
    solubility: Criterion | None = None
    compatibility: Criterion | None = None
    temperature: Criterion | None = None
    aroma: Criterion | None = None
    comparison_protocol: str = Field(min_length=3, max_length=120)


class Weights(StrictModel):
    oxidation: float = Field(default=25, ge=0, le=100)
    solubility: float = Field(default=25, ge=0, le=100)
    compatibility: float = Field(default=20, ge=0, le=100)
    temperature: float = Field(default=20, ge=0, le=100)
    aroma: float = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def total(self):
        if abs(sum(self.model_dump().values()) - 100) > 0.001:
            raise ValueError("Total bobot wajib 100%.")
        return self


class RankInput(StrictModel):
    formulation_ids: list[str] = Field(min_length=2, max_length=50)
    weights: Weights = Field(default_factory=Weights)
    comparison_protocol: str = Field(min_length=3, max_length=120)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.formulation_ids)) != len(self.formulation_ids):
            raise ValueError("Kandidat tidak boleh duplikat.")
        return self


class ExperimentInput(StrictModel):
    formulation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    batch_id: str = Field(min_length=2, max_length=100)
    protocol: str = Field(min_length=3, max_length=120)
    source_ref: str = Field(min_length=3, max_length=240)
    measured_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_h2o2: float = Field(gt=0, le=100)
    final_h2o2: float = Field(ge=0, le=100)
    ph: float = Field(ge=0, le=14)
    temperature_c: float = Field(ge=-20, le=100)
    duration_days: float = Field(gt=0, le=3650)
    homogeneous: bool
    aroma_intensity: float | None = Field(default=None, ge=0, le=5)
    notes: str = Field(default="", max_length=1500)
    data_origin: Literal["real", "synthetic"]
    confirmed_actual: bool = False

    @model_validator(mode="after")
    def actual(self):
        from datetime import date

        date.fromisoformat(self.measured_on)
        if self.data_origin == "real" and not self.confirmed_actual:
            raise ValueError("Konfirmasikan bahwa nilai berasal dari pengukuran lab nyata.")
        return self


class TrainInput(StrictModel):
    algorithm: Literal["catboost", "xgboost"]
    target: Literal["solubility", "h2o2_retention"]
    protocol: str = Field(default="", max_length=120)
