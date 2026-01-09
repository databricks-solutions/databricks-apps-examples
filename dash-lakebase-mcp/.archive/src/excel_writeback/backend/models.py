"""
Pydantic models for the Excel Writeback API.

Uses the 3-model pattern:
- Entity (DB model)
- EntityIn (input/create)
- EntityOut (output/response)
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .. import __version__


class VersionOut(BaseModel):
    version: str

    @classmethod
    def from_metadata(cls):
        return cls(version=__version__)


# ============================================================
# Layout Data Models
# ============================================================

class LayoutDataBase(BaseModel):
    """Base model for layout data fields"""
    layout_id: str = Field(..., alias="LAYOUT_ID")
    sell_id: str = Field(..., alias="SELL_ID")
    product_name: str = Field(..., alias="PRODUCT_NAME")
    loyalty_group: str = Field(..., alias="LOYALTY_GROUP")
    segment_1: str = Field(..., alias="SEGMENT_1")
    segment_2: str = Field(..., alias="SEGMENT_2")
    origin: str = Field(..., alias="ORIGIN")
    category_name: str = Field(..., alias="CATEGORY_NAME")
    subcategory_name: str = Field(..., alias="SUBCATEGORY_NAME")
    item_class_name: str = Field(..., alias="ITEM_CLASS_NAME")
    supplier: str = Field(..., alias="SUPPLIER")
    brand: str = Field(..., alias="BRAND")
    pack_size: str = Field(..., alias="PACK_SIZE")
    shelf_space_cm: float = Field(..., alias="SHELF_SPACE_CM")
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class LayoutDataIn(LayoutDataBase):
    """Input model for creating/updating layout data"""
    pass


class LayoutDataOut(LayoutDataBase):
    """Output model for layout data responses"""
    pass


class LayoutDataBatchIn(BaseModel):
    """Batch input for multiple layout data records"""
    records: List[LayoutDataIn]
    overwrite: bool = False


class LayoutDataBatchOut(BaseModel):
    """Response for batch operations"""
    success: bool
    rows_affected: int
    message: str


# ============================================================
# Forecast Models
# ============================================================

class ForecastSubmissionIn(BaseModel):
    """Input model for submitting a forecast"""
    records: List[LayoutDataIn]


class ForecastSubmissionOut(BaseModel):
    """Output model for forecast submission response"""
    forecast_id: str
    submission_timestamp: datetime
    row_count: int
    message: str


class ForecastSummaryOut(BaseModel):
    """Summary of a forecast"""
    forecast_id: str
    submission_timestamp: datetime
    row_count: int
    category_count: int


class ForecastListOut(BaseModel):
    """List of forecasts"""
    forecasts: List[ForecastSummaryOut]
    total: int


# ============================================================
# Stock Optimization Models
# ============================================================

class StockOptimizationOut(BaseModel):
    """Output model for stock optimization results"""
    forecast_id: str
    sell_id: str
    product_name: str
    category_name: str
    current_stock: int
    predicted_demand: float
    optimal_stock: int
    reorder_quantity: int
    confidence_score: float
    recommendation: str
    
    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class OptimizationSummaryOut(BaseModel):
    """Summary statistics for optimization results"""
    forecast_id: str
    total_products: int
    products_needing_reorder: int
    total_reorder_quantity: int
    avg_confidence_score: float


class OptimizationResultsOut(BaseModel):
    """Full optimization results with summary"""
    summary: OptimizationSummaryOut
    results: List[StockOptimizationOut]


# ============================================================
# Category Models
# ============================================================

class CategoryOut(BaseModel):
    """Output model for categories"""
    name: str
    product_count: int


class CategoriesListOut(BaseModel):
    """List of available categories"""
    categories: List[CategoryOut]
