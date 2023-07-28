#!/usr/bin/env python3
from quart import Quart, request
import tdxapi
from typing import Any
import os
import json
import time
import asset_lib


tdx = tdxapi.TeamDynamixInstance(
    domain="teamdynamix.umich.edu",
    auth_token=str(os.getenv("TDX_KEY")),
    default_asset_app_name="ITS EUC Assets/CIs",
    default_ticket_app_name="ITS Tickets"
)
app: Quart = Quart(__name__)


@app.before_serving
async def init() -> None:
    await tdx.initialize()

#####################
#                   #
#        TDX        #
#                   #
#####################


@app.route("/tdx/asset/<asset_tag>")  # type: ignore
async def get_asset(asset_tag: str) -> dict[str, Any]:
    assets: list[dict[str, Any]] = \
        await tdx.search_assets(asset_tag, "ITS EUC Assets/CIs")
    asset: dict[str, Any] = \
        await tdx.get_asset(assets[0]["ID"], "ITS EUC Assets/CIs")
    return asset


@app.get("/tdx/currentuser")  # type: ignore
async def get_current_user() -> dict[str, Any]:
    return tdx.get_current_user()


@app.get("/tdx/people/<uniqname>")  # type: ignore
async def get_person(uniqname: str) -> list[dict[str, Any]]:
    return tdx.search_people(uniqname)


@app.get("/tdx/ticket/<ticket_id>")  # type: ignore
async def get_ticket(ticket_id: str) -> dict[str, Any]:
    return tdx.get_ticket(ticket_id)


@app.post("/tdx/loan/checkout")  # type : ignore
async def checkout():
    data = await request.json
    return data["asset"]


@app.get("/test/sample_asset")  # type : ignore
async def test():
    with open('./resources/sample_asset.json') as asset_file:
        sample_asset = json.load(asset_file)
        time.sleep(5)
        return sample_asset
