from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .dependencies import get_current_consumer_identity
from .models import UsageLog
from .schemas import MeBalanceRead, UsageLogRead

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/credit-balance", response_model=MeBalanceRead)
def get_balance(identity=Depends(get_current_consumer_identity)):
    return MeBalanceRead(
        api_key_id=identity["api_key"].id,
        credit_balance=identity["api_key"].credit_balance,
        plan_name=identity["plan"].name,
        valid_from=identity["api_key"].valid_from,
        valid_until=identity["api_key"].valid_until,
    )


@router.get("/usage", response_model=list[UsageLogRead])
def get_usage(identity=Depends(get_current_consumer_identity), db: Session = Depends(get_db)):
    rows = (
        db.execute(select(UsageLog).where(UsageLog.api_key_id == identity["api_key"].id).order_by(UsageLog.created_at.desc()).limit(20))
        .scalars()
        .all()
    )
    return rows
