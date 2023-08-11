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
import asyncio

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


# @app.route("/tdx/asset/<asset_tag>")  # type: ignore
# async def get_asset(asset_tag: str) -> dict[str, Any]:
#     assets: list[dict[str, Any]] = \
#         await tdx.search_assets(asset_tag, "ITS EUC Assets/CIs")
#     asset: dict[str, Any] = \
#         await tdx.get_asset(assets[0]["ID"], "ITS EUC Assets/CIs")
#     return asset


# @app.get("/tdx/currentuser")  # type: ignore
# async def get_current_user() -> dict[str, Any]:
#     return tdx.get_current_user()


# @app.get("/tdx/people/<uniqname>")  # type: ignore
# async def get_person(uniqname: str) -> dict[str, Any]:
#     return await tdx.search_person(uniqname)


# @app.get("/tdx/ticket/<ticket_id>")  # type: ignore
# async def get_ticket(ticket_id: str) -> dict[str, Any]:
#     return tdx.get_ticket(ticket_id)

@app.post("/tdx/loan/return")  # type : ignore
async def dropoff():
    body = await request.json
    if not body:
        raise exceptions.MissingBodyException
    if "asset" not in body:
        raise exceptions.MalformedBodyException


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
    uniqname: str = body["uniqname"].lower()

    # Uncomment if needed for error checking
    # if uniqname == "mctester":
    #     raise tdxapi.exceptions.MultipleMatchesException("person")

    # Account for caps
    # Uniqname is 3-8 alpha characters
    if not uniqname_pattern.match(uniqname):
        raise exceptions.InvalidUniqnameException(uniqname)
    # Asset is SAHM, TRL, or SAH with digits
    if not asset_pattern.match(body["asset"]):
        raise exceptions.InvalidAssetException(body["asset"])

    # We can get everything we need for a loan from just the asset and uniqname
    # by searching for matching loan tickets requested by the uniqname, pulling
    # the approval status, loan date, and loaner type from the ticket. We make
    # sure the asset is valid to loan (not already out, etc), attach to the
    # request ticket, set location to Offsite, owner to provided uniqname,
    # update the last inventory date, and add on loan until to notes

    # Gather info

    owner_task: asyncio.Task[dict[str, Any]] = \
        asyncio.create_task(
            tdx.search_person(uniqname),
            name="Find Owner"
        )

    asset_task: asyncio.Task[dict[str, Any]] = \
        asyncio.create_task(
            asset_lib.find_asset(tdx, body["asset"]),
            name="Find Asset"
        )

    available_id: str = tdx.get_id(
        "ITS EUC Assets/CIs",
        "In Stock - Available",
        "AssetStatusIDs"
    )

    owner: dict[str, Any] = await owner_task
    ticket: dict[str, Any] = \
        await asset_lib.find_sah_request_ticket(tdx, owner)
    ticket = tdx.get_ticket(ticket["ID"], "ITS Tickets")
    loan_date = tdx.get_ticket_attribute(
        ticket,
        "sah_Loan Length (Term)"
    )["ValueText"]

    asset: dict[str, Any] = await asset_task
    if (asset["StatusID"] is not available_id):
        raise exceptions.AssetNotReadyToLoan(asset["Tag"])
    # ... and then everything else

    if "comment" not in body:
        body["comment"] = ""

    await asset_lib.check_out_asset(
        tdx,
        asset,
        ticket,
        owner,
        body["comment"]
    )
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


@app.errorhandler(
    tdxapi.exceptions.UniqnameDoesNotExistException
)  # type: ignore
async def handle_uniqname_not_found(
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


@app.errorhandler(exceptions.AssetNotFoundException)  # type: ignore
async def handle_object_not_found(
    error: exceptions.AssetNotFoundException
):
    response = {
        "error_number": 2,
        "message": error.message,
        "attributes": {
            "asset": error.asset
        }
    }
    return response, HTTPStatus.BAD_REQUEST


@app.errorhandler(tdxapi.exceptions.MultipleMatchesException)  # type: ignore
async def handle_multiple_matches(
    error: tdxapi.exceptions.MultipleMatchesException
):
    response = {
        "error_number": 3,
        "message": error.message,
        "attributes": {
            "type": error.type
        }
    }
    return response, HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.InvalidUniqnameException)  # type: ignore
async def handle_invalid_uniqname(
    error: exceptions.InvalidUniqnameException
):
    response = {
        "error_number": 4,
        "message": error.message,
        "attributes": {
            "uniqname": error.uniqname
        }
    }
    return response, HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.InvalidAssetException)  # type: ignore
async def handle_invalid_asset(
    error: exceptions.InvalidAssetException
):
    response = {
        "error_number": 5,
        "message": error.message,
        "attributes": {
            "asset": error.asset
        }
    }
    return response, HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.NoLoanRequestException)  # type: ignore
async def handle_no_loan_request(
    error: exceptions.NoLoanRequestException
):
    response = {
        "error_number": 6,
        "message": error.message,
        "attributes": {
            "uniqname": error.uniqname
        }
    }
    return response, HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.AssetNotReadyToLoan)  # type: ignore
async def handle_asset_not_ready(
    error: exceptions.AssetNotReadyToLoan
):
    response = {
        "error_number": 7,
        "message": error.message,
        "attributes": {
            "asset": error.asset,
        }
    }
    return response, HTTPStatus.BAD_REQUEST
