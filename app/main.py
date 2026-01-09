from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .parking_feed import FeedCache

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

cache = FeedCache(ttl_seconds=15)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    lots = cache.get()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "lots": lots,
        },
    )

@app.get("/fragment/parkinglots")
def fragment_parkinglots(request: Request):
    return templates.TemplateResponse("_table.html", {
        "request": request,
        "lots": cache.get()
    })
