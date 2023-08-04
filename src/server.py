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
import exceptions
import re

# Regex patterns

# 3-8 alpha characters
uniqname_pattern: re.Pattern[str] = re.compile("^[a-z]{3,8}$")

# TRL or SAH then 5 digits, or SAHM then 4 digits
asset_pattern: re.Pattern[str] = \
    re.compile("^((TRL|SAH)[0-9]{5})|SAHM[0-9]{4}")

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
async def get_person(uniqname: str) -> dict[str, Any]:
    return await tdx.search_person(uniqname)


@app.get("/tdx/ticket/<ticket_id>")  # type: ignore
async def get_ticket(ticket_id: str) -> dict[str, Any]:
    return tdx.get_ticket(ticket_id)


@app.post("/tdx/loan/checkout")  # type : ignore
async def checkout():
    body = await request.json

    # Error checking
    if not body:
        raise exceptions.MissingBodyException 
    
    # Uniqname and asset are the only required parts of the body
    if "uniqname" not in body:
        raise exceptions.MalformedBodyException
    if "asset" not in body:
        raise exceptions.MalformedBodyException
    
    uniqname: str = body["uniqname"].lower()  # Account for caps

    if not uniqname_pattern.match(uniqname):  # Uniqname is 3-8 alpha characters
        raise exceptions.InvalidUniqnameException

    if not asset_pattern.match(body["asset"]):  # Asset is SAHM, TRL, or SAH with digits
        raise exceptions.InvalidAssetException

    # We can get everything we need for a loan from just the asset and uniqname
    # by searching for matching loan tickets requested by the uniqname, pulling
    # the approval status, loan date, and loaner type from the ticket. We make
    # sure the asset is valid to loan (not already out, etc), attach to the
    # request ticket, set location to Offsite, owner to provided uniqname,
    # update the last inventory date, and add on loan until to notes

    # Gather info
    owner: dict[str, Any] = await tdx.search_person(uniqname) 

    asset: dict[str, Any] = await asset_lib.find_asset(tdx, body["asset"])

    ticket: dict[str, Any] = \
        await asset_lib.find_sah_request_ticket(tdx, owner["UID"])
    ticket = tdx.get_ticket(ticket["ID"], "ITS Tickets")
    loan_date = tdx.get_ticket_attribute(
        ticket,
        "sah_Loan Length (Term)"
    )["ValueText"]

    # ... and then everything else
    await asset_lib.check_out_asset(tdx, asset, ticket, owner)

    # Give some useful info back to the front end to display to user
    response: dict[str, dict[str, Any]] = {
        "asset": {
            "tag": asset["Tag"],
            "id": asset["ID"],
        },
        "loan": {
            "name": ticket["RequestorName"],
            "date": loan_date,
            "uniqname": owner["AlternateID"]
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


@app.errorhandler(tdxapi.exceptions.UniqnameDoesNotExistException)  # type: ignore
async def handle_no_uniqname(
        error: tdxapi.exceptions.UniqnameDoesNotExistException
    ):
    response: dict[str, int | Any | dict[str, Any]] = {
        "error_number": 1,
        "message": error.message,
        "attributes": {
            "uniqname": error.uniqname
        }
    }
    return response, HTTPStatus.BAD_REQUEST
