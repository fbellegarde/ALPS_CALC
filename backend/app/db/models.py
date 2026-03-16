from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .database import Base

class AlpsShiftLog(Base):
    __tablename__ = "alps_shift_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    operating_date = Column(String, index=True)
    shift_name = Column(String)
    volume = Column(Float)
    sched_hc = Column(Float)
    ai_predicted_tph = Column(Float)
    ai_predicted_absence = Column(Float)
    action_required = Column(String)
    action_category = Column(String, index=True) # SURPLUS or DEFICIT
    end_backlog_risk = Column(Integer)
    historical_feedback = Column(String)