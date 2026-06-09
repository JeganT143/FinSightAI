from pydantic import BaseModel, field_validator


class ResearchRequest(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        ticker = v.upper().strip()
        if not ticker.isalpha():
            raise ValueError("Ticker must only contain letters")
        if len(ticker) > 5:
            raise ValueError("Ticker must be at most 5 characters long")
        return ticker


class ResearchResponse(BaseModel):
    ticker: str
    report: str
    status: str
    was_revised: bool
