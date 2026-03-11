"""
Inheritance Calculator API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional
from app.core.database import get_db
from app.api.routes.auth import get_current_user
from app.services.inheritance_calculator import calculate_inheritance

router = APIRouter(prefix="/inheritance", tags=["Inheritance"])


class HeirInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    relationship: str
    gender: str = "male"
    count: int = Field(default=1, ge=1, le=10)


class PropertyInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    property_type: str = "general"  # real_estate, cash, gold, vehicle, shares, other
    value: float = Field(..., gt=0)


class InheritanceRequest(BaseModel):
    religion: str = Field(..., description="sunni_hanafi, shia, christian, hindu, sikh")
    deceased_name: str = Field(default="Deceased", max_length=100)
    heirs: list[HeirInput]
    properties: list[PropertyInput] = []
    total_estate: Optional[float] = None  # If not provided, sum of properties
    debts: float = Field(default=0, ge=0)
    bequests: float = Field(default=0, ge=0)


class InheritanceResponse(BaseModel):
    success: bool
    data: dict
    properties_breakdown: list[dict] = []


@router.post("/calculate", response_model=InheritanceResponse)
async def calculate(
    req: InheritanceRequest,
    current_user=Depends(get_current_user),
):
    """Calculate inheritance distribution based on the selected legal system."""
    # Calculate total estate from properties if not provided
    total_estate = req.total_estate
    if not total_estate and req.properties:
        total_estate = sum(p.value for p in req.properties)
    elif not total_estate:
        raise HTTPException(status_code=400, detail="Provide total_estate or at least one property")

    if total_estate <= 0:
        raise HTTPException(status_code=400, detail="Total estate must be greater than 0")

    if not req.heirs:
        raise HTTPException(status_code=400, detail="At least one heir is required")

    heirs_data = [h.model_dump() for h in req.heirs]

    try:
        result = calculate_inheritance(
            religion=req.religion,
            heirs_data=heirs_data,
            total_estate=total_estate,
            debts=req.debts,
            bequests=req.bequests,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Per-property breakdown
    properties_breakdown = []
    if req.properties:
        for prop in req.properties:
            prop_ratio = prop.value / total_estate if total_estate > 0 else 0
            prop_result = {
                "property_name": prop.name,
                "property_type": prop.property_type,
                "property_value": prop.value,
                "shares": [],
            }
            for heir in result["heirs"]:
                prop_result["shares"].append({
                    "heir_name": heir["name"],
                    "relationship": heir["relationship"],
                    "share_percentage": heir["share_percentage"],
                    "share_amount": round(heir["share_amount"] * prop_ratio, 2),
                })
            properties_breakdown.append(prop_result)

    return InheritanceResponse(
        success=True,
        data=result,
        properties_breakdown=properties_breakdown,
    )


@router.get("/relationships")
async def get_relationships(current_user=Depends(get_current_user)):
    """Get list of valid heir relationships."""
    return {
        "relationships": [
            {"value": "husband", "label": "Husband", "gender": "male", "info": "Must be legally married."},
            {"value": "wife", "label": "Wife", "gender": "female", "info": "Multiple wives eligible. Divorced wife eligible if iddah not completed."},
            {"value": "son", "label": "Son", "gender": "male", "info": "Adopted, step, or illegitimate son not eligible."},
            {"value": "daughter", "label": "Daughter", "gender": "female", "info": "Adopted, step, or illegitimate daughter not eligible."},
            {"value": "father", "label": "Father", "gender": "male", "info": "Step-father or illegitimate father not eligible."},
            {"value": "mother", "label": "Mother", "gender": "female", "info": "Step-mother or illegitimate mother not eligible."},
            {"value": "sons_son", "label": "Grandson (Son's Son)", "gender": "male", "info": "Only son's sons. Daughter's sons not eligible."},
            {"value": "sons_daughter", "label": "Granddaughter (Son's Daughter)", "gender": "female", "info": "Only son's daughters. Daughter's daughters not eligible."},
            {"value": "paternal_grandfather", "label": "Paternal Grandfather", "gender": "male", "info": "Father's father only. Mother's father not eligible."},
            {"value": "paternal_grandmother", "label": "Paternal Grandmother", "gender": "female", "info": "Father's mother."},
            {"value": "maternal_grandmother", "label": "Maternal Grandmother", "gender": "female", "info": "Mother's mother."},
            {"value": "full_brother", "label": "Full Brother", "gender": "male", "info": "Same father and mother as deceased."},
            {"value": "full_sister", "label": "Full Sister", "gender": "female", "info": "Same father and mother as deceased."},
            {"value": "paternal_half_brother", "label": "Paternal Half Brother", "gender": "male", "info": "Same father, different mother."},
            {"value": "paternal_half_sister", "label": "Paternal Half Sister", "gender": "female", "info": "Same father, different mother."},
            {"value": "maternal_half_brother", "label": "Maternal Half Brother", "gender": "male", "info": "Same mother, different father."},
            {"value": "maternal_half_sister", "label": "Maternal Half Sister", "gender": "female", "info": "Same mother, different father."},
            {"value": "full_nephew", "label": "Full Nephew", "gender": "male", "info": "Full brother's son only."},
            {"value": "paternal_nephew", "label": "Paternal Nephew", "gender": "male", "info": "Paternal brother's son only."},
            {"value": "full_nephews_son", "label": "Full Nephew's Son", "gender": "male", "info": "Full brother's son's son."},
            {"value": "paternal_nephews_son", "label": "Paternal Nephew's Son", "gender": "male", "info": "Paternal brother's son's son."},
            {"value": "full_paternal_uncle", "label": "Full Paternal Uncle", "gender": "male", "info": "Father's full brother."},
            {"value": "paternal_paternal_uncle", "label": "Paternal Paternal Uncle", "gender": "male", "info": "Father's paternal brother."},
            {"value": "full_cousin", "label": "Full Cousin", "gender": "male", "info": "Father's full brother's son."},
            {"value": "paternal_cousin", "label": "Paternal Cousin", "gender": "male", "info": "Father's paternal brother's son."},
            {"value": "full_cousins_son", "label": "Full Cousin's Son", "gender": "male", "info": "Father's full brother's son's son."},
            {"value": "paternal_cousins_son", "label": "Paternal Cousin's Son", "gender": "male", "info": "Father's paternal brother's son's son."},
            {"value": "full_cousins_grandson", "label": "Full Cousin's Grandson", "gender": "male", "info": "Father's full brother's son's son's son."},
            {"value": "paternal_cousins_grandson", "label": "Paternal Cousin's Grandson", "gender": "male", "info": "Father's paternal brother's son's son's son."},
        ],
        "religions": [
            {"value": "sunni_hanafi", "label": "Islamic (Sunni - Hanafi)", "description": "Predominant in Pakistan"},
            {"value": "shia", "label": "Islamic (Shia - Jafari)", "description": "Ithna Ashari school"},
            {"value": "christian", "label": "Christian", "description": "Succession Act 1925"},
            {"value": "hindu", "label": "Hindu", "description": "Hindu Succession Law"},
            {"value": "sikh", "label": "Sikh", "description": "Customary / Succession Act 1925"},
        ],
        "property_types": [
            {"value": "real_estate", "label": "Real Estate / Land"},
            {"value": "cash", "label": "Cash / Bank Balance"},
            {"value": "gold", "label": "Gold / Jewelry"},
            {"value": "vehicle", "label": "Vehicle"},
            {"value": "shares", "label": "Shares / Investments"},
            {"value": "business", "label": "Business Assets"},
            {"value": "other", "label": "Other"},
        ],
    }
