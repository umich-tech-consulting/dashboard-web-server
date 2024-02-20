from flask import Flask, request, jsonify
import tdxapi
import sahlib
from http import HTTPStatus
import exceptions
import re
import asyncio
from aiohttp import ClientError
import yaml

with open("dashboard.yml") as config_file:
    config = yaml.safe_load(config_file)

# Regex patterns
uniqname_pattern = re.compile("^[a-z]{3,8}$")
asset_pattern = re.compile("^((TRL|SAH)[0-9]{5})|SAHM[0-9]{4}")

tdx = tdxapi.TeamDynamixInstance(
    domain=config["domain"],
    sandbox=config["sandbox"],
    default_asset_app_name=config["default_app_names"]["asset"],
    default_ticket_app_name=config["default_app_names"]["ticket"],
)

app = Flask(__name__)


async def init_async():
    await tdx.login()
    await tdx.load_ids()
    await tdx.initialize()


with app.app_context():
    asyncio.run(init_async())


#####################
#                   #
#        TDX        #
#                   #
#####################


@app.route("/tdx/currentuser", methods=["GET"])
def currentuser():
    return jsonify(tdx.get_current_user())


@app.route("/tdx/loan/return", methods=["POST"])
def dropoff():
    body = request.json
    if not body:
        raise exceptions.MissingBodyException
    if "asset" not in body:
        raise exceptions.MalformedBodyException
    if not asset_pattern.match(body["asset"]):
        raise exceptions.InvalidAssetException(body["asset"])

    asset = asyncio.run(sahlib.find_asset(tdx, body["asset"]))
    available_id = tdx.get_id(
        "ITS EUC Assets/CIs", "In Stock - Available", "AssetStatusIDs"
    )
    if asset["StatusID"] == available_id:
        raise exceptions.AssetAlreadyCheckedInException(asset["Tag"])
    if "comment" not in body:
        body["comment"] = ""
    person = asyncio.run(tdx.get_person(asset["OwningCustomerID"]))
    asyncio.run(sahlib.check_in_asset(tdx, asset, comment=body["comment"]))

    response = {
        "asset": {"tag": asset["Tag"], "id": asset["ID"], "comment": body["comment"]},
        "previous_owner": {"uniqname": person["AlternateID"], "uid": person["UID"]},
    }

    return jsonify(response), HTTPStatus.OK


@app.route("/tdx/loan/checkout", methods=["POST"])
def checkout():
    body = request.json
    if not body:
        raise exceptions.MissingBodyException
    if "uniqname" not in body:
        raise exceptions.MalformedBodyException
    if "asset" not in body:
        raise exceptions.MalformedBodyException
    uniqname = body["uniqname"].lower()
    if not uniqname_pattern.match(uniqname):
        raise exceptions.InvalidUniqnameException(uniqname)
    if not asset_pattern.match(body["asset"]):
        raise exceptions.InvalidAssetException(body["asset"])

    owner = asyncio.run(tdx.search_person({"AlternateID": uniqname}))
    ticket = asyncio.run(sahlib.find_sah_request_ticket(tdx, owner))
    ticket = tdx.get_ticket(ticket["ID"], "ITS Tickets")

    approval_attribute = tdx.get_ticket_attribute(ticket, "sah_Request Status")
    if approval_attribute["Value"] == 43075:
        exceptions.LoanRequestDeniedException(
            ticket=ticket["ID"], requester=owner["AlternateID"]
        )
    if approval_attribute["Value"] not in [43072, 43071]:
        exceptions.NoLoanRequestException(owner["AlternateID"])

    ticket_assets = asyncio.run(tdx.get_ticket_assets(ticket["ID"]))
    if len(ticket_assets) > 0:
        already_loaned_asset = asyncio.run(
            tdx.get_asset(ticket_assets[0]["BackingItemID"])
        )
        raise exceptions.LoanAlreadyFulfilledException(
            ticket["ID"], already_loaned_asset["Tag"]
        )

    loan_date = tdx.get_ticket_attribute(ticket, "sah_Loan Length (Open date)")[
        "ValueText"
    ]

    asset = asyncio.run(sahlib.find_asset(tdx, body["asset"]))
    available_id = tdx.get_id(
        "ITS EUC Assets/CIs", "In Stock - Available", "AssetStatusIDs"
    )
    if asset["StatusID"] != available_id:
        raise exceptions.AssetNotReadyToLoanException(asset["Tag"])
    if (
        approval_attribute["ValueText"] == "Windows" and "SAH0" not in asset["Tag"]
    ) or (approval_attribute["ValueText"] == "Mac" and "SAHM" not in asset["Tag"]):
        raise exceptions.WrongAssetTypeException(
            ticket["ID"], approved_type=approval_attribute["ValueText"]
        )

    if "comment" not in body:
        body["comment"] = ""

    asyncio.run(sahlib.check_out_asset(tdx, asset, ticket, owner, body["comment"]))

    response = {
        "asset": {"tag": asset["Tag"], "id": asset["ID"], "comment": body["comment"]},
        "loan": {
            "name": ticket["RequestorName"],
            "date": loan_date,
            "uniqname": owner["AlternateID"],
            "owner_uid": owner["UID"],
        },
        "ticket": {"id": ticket["ID"]},
    }

    return jsonify(response), HTTPStatus.OK


@app.errorhandler(tdxapi.exceptions.PersonDoesNotExistException)
def handle_uniqname_not_found(error):
    response = {
        "error_number": 1,
        "message": error.message,
        "attributes": {
            "uniqname": error.criteria["AlternateID"],
            "criteria": error.criteria,
        },
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.AssetNotFoundException)
def handle_object_not_found(error):
    response = {
        "error_number": 2,
        "message": error.message,
        "attributes": {"asset": error.asset},
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(tdxapi.exceptions.MultipleMatchesException)
def handle_multiple_matches(error):
    response = {
        "error_number": 3,
        "message": error.message,
        "attributes": {"type": error.type},
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.InvalidUniqnameException)
def handle_invalid_uniqname(error):
    response = {
        "error_number": 4,
        "message": error.message,
        "attributes": {"uniqname": error.uniqname},
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.InvalidAssetException)
def handle_invalid_asset(error):
    response = {
        "error_number": 5,
        "message": error.message,
        "attributes": {"asset": error.asset},
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.NoLoanRequestException)
def handle_no_loan_request(error):
    response = {
        "error_number": 6,
        "message": error.message,
        "attributes": {"uniqname": error.uniqname},
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.AssetNotReadyToLoanException)
def handle_asset_not_ready(error):
    response = {
        "error_number": 7,
        "message": error.message,
        "attributes": {
            "asset": error.asset,
        },
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.AssetAlreadyCheckedInException)
def handle_asset_already_available(error):
    response = {
        "error_number": 8,
        "message": error.message,
        "attributes": {
            "asset": error.asset,
        },
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(ClientError)
def handle_tdx_communication_error(error):
    response = {
        "error_number": 9,
        "message": "Unable to connect to TDx or slow response",
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(tdxapi.exceptions.UnableToAttachAssetException)
def handle_asset_attach_failure(error):
    response = {
        "error_number": 10,
        "message": error.message,
        "attributes": {"ticket": error.ticket, "asset": error.asset},
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.LoanAlreadyFulfilledException)
def handle_loan_already_fulfilled(error):
    response = {
        "error_number": 11,
        "message": error.message,
        "attributes": {"ticket": error.ticket, "asset": error.asset},
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.WrongAssetTypeException)
def handle_wrong_asset_approved(error):
    response = {
        "error_number": 12,
        "message": error.message,
        "attributes": {
            "approved_type": error.approved_type,
        },
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


@app.errorhandler(exceptions.LoanRequestDeniedException)
def handle_loan_request_denied(error):
    response = {
        "error_number": 13,
        "message": error.message,
    }
    return jsonify(response), HTTPStatus.BAD_REQUEST


if __name__ == "__main__":
    app.run(debug=True)
