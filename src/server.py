#!/usr/bin/env python3
from quart import Quart, request
import tdxapi
from typing import Any
import os
import json
import time
import asset_lib
from http import HTTPStatus
import quart_cors

tdx = tdxapi.TeamDynamixInstance(
    domain="teamdynamix.umich.edu",
    sandbox=True,
    auth_token=str(os.getenv("TDX_KEY")),
    default_asset_app_name="ITS EUC Assets/CIs",
    default_ticket_app_name="ITS Tickets"
)
app: Quart = Quart(__name__)
app = quart_cors.cors(app, allow_origin="*")


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
    body = await request.json
    if not body:
        return "No body!"
    if "uniqname" not in body:
        return "Request must include uniqname", HTTPStatus.BAD_REQUEST
    if len(body["uniqname"]) < 3 or len(body["uniqname"]) > 8:
        return "Uniqnames must be \
              between 3 and 8 characters", HTTPStatus.BAD_REQUEST

    if "asset" not in body:
        return "Request must include asset tag", HTTPStatus.BAD_REQUEST
    if body["asset"][:3] not in ["SAH", "TRL"]:
        return f"Asset prefix must be SAH or TRL,\
              got {body['asset'][:3]}", HTTPStatus.BAD_REQUEST

    owner_uid: str = asset_lib.find_person_uid(tdx, body["uniqname"])
    asset: dict[str, Any] = await asset_lib.find_asset(tdx, body["asset"])

    ticket: dict[str, Any] = asset_lib.find_sah_request_ticket(tdx, owner_uid)

    ticket = tdx.get_ticket(ticket["ID"], "ITS Tickets")
    loan_date = tdx.get_ticket_attribute(ticket, "sah_Loan Length (Term)")["ValueText"]
    await asset_lib.check_out_asset(tdx, asset, ticket, owner_uid)

    response = {
        "asset": {
            "tag": asset["Tag"],
            "id": asset["ID"],
        },
        "loan": {
            "name": ticket["RequestorName"],
            "date": loan_date,
            "owner_uid": owner_uid
        },
        "ticket": {
            "id": ticket["ID"]
        }
    }

    return response, HTTPStatus.OK


@app.get("/test/sample_asset")  # type : ignore
async def test():
    with open('./resources/sample_asset.json') as asset_file:
        sample_asset = json.load(asset_file)
        time.sleep(5)
        return sample_asset
