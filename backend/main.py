from fastapi import FastAPI, HTTPException

from load import load_all
from metrics import loss_experience

app = FastAPI()

# Loaded and cleaned once at startup, not on every request.
DATA = load_all()
PORTFOLIOS = {p["portfolio_id"] for p in DATA["policies"].values()}


@app.get("/portfolios/{portfolio_id}/loss-experience")
def loss(portfolio_id: str):
    if portfolio_id not in PORTFOLIOS:
        raise HTTPException(status_code=404, detail=f"Portfolio with id {portfolio_id} does not exist")
    return {
        "portfolio_id": portfolio_id,
        "currency": "DKK",
        "perils": loss_experience(DATA["policies"], DATA["claims"], portfolio_id),
    }
