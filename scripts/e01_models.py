"""E01 canonical 데이터 스키마 (pydantic). 필드 정의는 docs/manufacturing_data_schema.md §3.

필드 단위 형식·범위 검증만 한다. 엔터티 간 참조·BOM 구조 검증은 e01_verify.py가 독립적으로 수행한다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    record_uid: str = Field(pattern=r"^rec_[0-9a-f]{16}$")
    origin_class: Literal["SYNTHETIC", "PUBLIC_DERIVED"]


class Unit(_Base):
    unit_code: str
    dimension: Literal["MASS", "COUNT", "TIME"]
    base_unit_code: str
    to_base_factor: Decimal = Field(gt=0)


class Product(_Base):
    product_id: str
    product_name: str
    product_type: Literal["FINISHED", "SEMI_FINISHED"]
    base_unit: str
    safety_stock_qty: Decimal = Field(ge=0)
    manuf_lead_time_days: int = Field(ge=0)
    outsourcing_allowed: bool
    outsourcing_unit_cost: Optional[Decimal] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _outsourcing(self):
        if self.outsourcing_allowed != (self.outsourcing_unit_cost is not None):
            raise ValueError("outsourcing_unit_cost는 outsourcing_allowed=True일 때만 있어야 함")
        return self


class Material(_Base):
    material_id: str
    material_name: str
    base_unit: str
    unit_cost: Decimal = Field(ge=0)
    safety_stock_qty: Decimal = Field(ge=0)


class Supplier(_Base):
    supplier_id: str
    supplier_name: str


class SupplierMaterial(_Base):
    supplier_id: str
    material_id: str
    lead_time_days: int = Field(ge=0)
    min_order_qty: Optional[Decimal] = Field(default=None, ge=0)
    is_preferred: bool


class BOM(_Base):
    bom_id: str
    product_id: str
    bom_version: str
    status: Literal["DRAFT", "APPROVED"]
    is_active: bool
    valid_from: dt.date
    valid_to: Optional[dt.date] = None
    min_qty: Decimal = Field(ge=0)
    max_qty: Optional[Decimal] = None
    site_id: Optional[str] = None
    base_qty: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def _ranges(self):
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to < valid_from")
        if self.max_qty is not None and self.max_qty <= self.min_qty:
            raise ValueError("max_qty <= min_qty")
        if self.is_active and self.status != "APPROVED":
            raise ValueError("활성 버전은 APPROVED여야 함")
        return self


class BOMLine(_Base):
    bom_id: str
    line_no: int = Field(ge=1)
    component_type: Literal["MATERIAL", "PRODUCT"]
    component_material_id: Optional[str] = None
    component_product_id: Optional[str] = None
    qty_per: Decimal = Field(gt=0)
    unit: str
    scrap_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    line_type: Literal["ITEM"] = "ITEM"

    @model_validator(mode="after")
    def _component(self):
        is_mat = self.component_type == "MATERIAL"
        if is_mat != (self.component_material_id is not None) or is_mat == (self.component_product_id is not None):
            raise ValueError("component_type과 구성품 ID 열이 맞지 않음")
        return self


class Order(_Base):
    order_id: str
    product_id: str
    order_qty: Decimal = Field(gt=0)
    unit: str
    order_date: dt.date
    due_date: dt.date
    priority: Literal["NORMAL", "URGENT"]
    status: Literal["OPEN", "CLOSED", "CANCELLED"]

    @model_validator(mode="after")
    def _dates(self):
        if self.due_date < self.order_date:
            raise ValueError("due_date < order_date")
        return self


class SalesHistory(_Base):
    product_id: str
    period_start: dt.date
    period_grain: Literal["DAY", "WEEK"]
    sales_qty: Decimal = Field(ge=0)
    source_series_id: Optional[str] = None
    generation_method: Literal["GENERATED", "ALLOCATED", "MAPPED", "TRANSFORMED"]
    derived_from_record_uid: Optional[str] = None
    allocation_share: Optional[Decimal] = Field(default=None, gt=0, le=1)
    date_is_synthetic: bool = False
    source_day_of_week_code: Optional[int] = None  # 공개 원본의 요일 코드 숫자 그대로 (의미 미확인)

    @model_validator(mode="after")
    def _allocation(self):
        if self.generation_method == "ALLOCATED" and (self.derived_from_record_uid is None or self.allocation_share is None):
            raise ValueError("ALLOCATED에는 원본 레코드와 배분 비율이 필요")
        return self


class Inventory(_Base):
    item_type: Literal["PRODUCT", "MATERIAL"]
    item_id: str
    as_of_date: dt.date
    on_hand_qty: Decimal = Field(ge=0)
    allocated_qty: Decimal = Field(default=Decimal("0"), ge=0)
    on_order_qty: Decimal = Field(default=Decimal("0"), ge=0)
    expected_receipt_date: Optional[dt.date] = None
    unit: str

    @model_validator(mode="after")
    def _qty(self):
        if self.allocated_qty > self.on_hand_qty:
            raise ValueError("allocated_qty > on_hand_qty")
        if self.on_order_qty > 0 and self.expected_receipt_date is None:
            raise ValueError("입고 예정 수량에 예정일 없음")
        return self


class Resource(_Base):
    resource_id: str
    resource_name: str
    resource_type: Literal["MACHINE", "LINE", "WORKCENTER"]
    regular_hours_per_day: Decimal = Field(gt=0)
    overtime_hours_per_day_max: Decimal = Field(ge=0)
    cost_per_hour: Decimal = Field(ge=0)
    overtime_cost_per_hour: Decimal = Field(ge=0)


class Operation(_Base):
    operation_id: str
    product_id: str
    sequence_no: int = Field(ge=1)
    resource_id: str
    run_time_per_unit_h: Decimal = Field(gt=0)
    setup_time_h: Decimal = Field(ge=0)


class ProductionPlan(_Base):
    plan_id: str
    plan_name: str
    horizon_start: dt.date
    horizon_end: dt.date
    generated_by: Literal["RULE", "OPTIMIZER", "MANUAL"]
    overtime_allowed: bool  # 잔업안만 True: 자체 생산 가용시간 = 정규 + 잔업 최대


class ProductionPlanLine(_Base):
    plan_id: str
    line_no: int = Field(ge=1)
    product_id: str
    period_start: dt.date
    planned_qty: Decimal = Field(ge=0)
    unit: str
    production_mode: Literal["INHOUSE", "OUTSOURCE"]  # v2: 잔업 여부는 라인이 아니라 계획(overtime_allowed)으로 정함
    resource_id: Optional[str] = None

    @model_validator(mode="after")
    def _mode(self):
        if (self.production_mode == "OUTSOURCE") != (self.resource_id is None):
            raise ValueError("외주 라인만 resource_id가 비어 있어야 함")
        return self


MODELS = {
    "Unit": Unit, "Product": Product, "Material": Material, "Supplier": Supplier,
    "SupplierMaterial": SupplierMaterial, "BOM": BOM, "BOMLine": BOMLine, "Order": Order,
    "SalesHistory": SalesHistory, "Inventory": Inventory, "Resource": Resource, "Operation": Operation,
    "ProductionPlan": ProductionPlan, "ProductionPlanLine": ProductionPlanLine,
}


def validate_entities(entities: dict[str, list[dict]]) -> dict[str, int]:
    """모든 레코드를 모델로 검증하고 엔터티별 개수를 돌려준다. 실패 시 ValidationError."""
    missing = set(MODELS) - set(entities)
    if missing:
        raise ValueError(f"엔터티 누락: {sorted(missing)}")
    return {name: len([MODELS[name].model_validate(r) for r in rows]) for name, rows in entities.items()}
