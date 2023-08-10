"""Useful functions for managing consulting loaners.

Returns:
    _type_: _description_
"""

from datetime import date
from typing import Any, Optional
import tdxapi
import exceptions


async def inventory_asset(  # pylint: disable=too-many-arguments
    tdx: tdxapi.TeamDynamixInstance,
    asset: dict[str, Any],
    location_name: str,
    status_name: str,
    owner_uid: str = "",
    notes: str = "",
    app_name: str = "",
    update_inv_date: bool = False
) -> None:
    """Update asset status.

    Updates the inventory status of an asset by updating location,
    status, owner, and notes

    Args:
        asset (dict):
        Asset to update

        app_name (str):
        Asset app the asset exists in

        location_name (str):
        New location name, must correlate to an ID already in TDx

        status_name (str):
        New status name, must correlate to an ID already in TDx

        owner_uid (str):
        New owner of the asset, removes owner if not given

        notes (str):
        New notes if provided, keeps previous notes if none given
    """
    if app_name == "":
        app_name = tdx.get_default_app_name("Asset")
    asset["LocationID"] = tdx.get_id("LocationIDs", location_name)
    asset["StatusID"] = tdx.get_id(app_name, status_name, "AssetStatusIDs")
    if not owner_uid:
        asset["OwningCustomerID"] = tdx.no_owner_uid
    else:
        asset["OwningCustomerID"] = owner_uid
    existing_attributes: list[str] = []
    for attr in asset["Attributes"]:
        existing_attributes.append(attr["Name"])
        if attr["Name"] == "Notes":
            attr["Value"] = notes
        if attr["Name"] == "Last Inventoried":
            attr["Value"] = date.today().strftime("%m/%d/%Y")
    if "Last Inventoried" not in existing_attributes and update_inv_date:
        asset["Attributes"].append(
            {
                "ID": tdx.get_id("AssetAttributes", "Last Inventoried"),
                "Value": date.today().strftime("%m/%d/%Y"),
            }
        )
    if "Notes" not in existing_attributes and notes != "":
        asset["Attributes"].append(
            {
                "ID": tdx.get_id("AssetAttributes", "Notes"),
                "Value": notes,
            }
        )
    await tdx.update_asset(asset)


async def find_asset(
        tdx: tdxapi.TeamDynamixInstance, asset_tag: str
) -> dict[str, Any]:
    """Find an asset based on tag.

    Args:
        tdx (tdxapi.TeamDynamixInstance): TeamDynamix instance to search
        asset_tag (str): Asset tag to searched

    Returns:
        dict[str, Any]: Returns an asset dictionary
    """
    print(f"Searching for asset {asset_tag}...")
    assets: list[dict[str, Any]] = await tdx.search_assets(asset_tag)
    if len(assets) == 0:
        raise exceptions.AssetNotFoundException(asset_tag)
    elif len(assets) > 1:
        raise tdxapi.exceptions.MultipleMatchesException("")
    else:
        asset = await tdx.get_asset(assets[0]["ID"])
        print(f"Found asset {asset_tag}")
        return asset


# async def find_person_uid(
#   tdx: tdxapi.TeamDynamixInstance,
#   uniqname: str) -> str:
#     """Find the UID of a person in TDx based on uniqname.

#     Args:
#         tdx (tdxapi.TeamDynamixInstance): _description_
#         uniqname (str): _description_

#     Returns:
#         str: _description_
#     """

#     people = await tdx.search_people(uniqname)
#     print(f"Found person with uniqname {uniqname}")
#     person_uid = people[0]["UID"]
#     return person_uid


async def find_sah_request_ticket(
    tdx: tdxapi.TeamDynamixInstance, person: dict[str, Any]
) -> dict[str, Any]:
    """Find a ticket assigned to ITS-Sitesathome with title Sites@Home Request.

    Args:
        tdx (tdxapi.TeamDynamixInstance): TeamDynamix instance
        person_uid (str): UID of person in TeamDynamix

    Returns:
        dict: Latest matching ticket
    """
    print("Searching for Sites@Home request tickets")
    criteria = {
        "RequestorUids": [person["UID"]],
        "FormIDs": [tdx.get_id(
            "ITS Tickets",
            "ITS-Sites @ Home - Form",
            "TicketFormIDs"
        )]

    }
    tickets: list[dict[str, Any]] = tdx.search_tickets(
        title="Sites @ Home Request",
        criteria=criteria
    )
    if len(tickets) == 0:
        raise exceptions.NoLoanRequestException(person["AlternateID"])

    elif len(tickets) > 1:
        raise tdxapi.exceptions.MultipleMatchesException("person")
    else:
        ticket: dict[str, Any] = tdx.get_ticket(tickets[0]["ID"])
        print(f"Found ticket TDx {ticket['ID']}")
        return ticket


# def find_sah_drop_off_ticket(
#     tdx: tdxapi.TeamDynamixInstance, person_uid: str
# ) -> dict[str, Any]:
#     """Find return request for Sites at Home laptop.

#     Find a ticket assigned to ITS-SitesatHome with title\
#     IMPORTANT: Sites@Home Laptop Return or Extension.

#     Args:
#         tdx (tdxapi.TeamDynamixInstance): _description_
#         person_uid (str): _description_

#     Returns:
#         dict: _description_
#     """
#     print("Searching for Sites@Home return tickets")
#     tickets: list[dict[str, Any]] = tdx.search_tickets(
#         person_uid,
#         [
#             "New",
#             "Open",
#             "Scheduled",
#         ],
#         "IMPORTANT: Sites@Home Laptop Return or Extension",
#         "ITS-SitesatHome",
#     )
#     if len(tickets) == 0:
#         raise tdxapi.ObjectNotFoundException
#     elif len(tickets) > 1:
#         ticket = _multiple_matches_chooser(tickets, "ID")
#         return ticket
#     else:
#         ticket = tdx.get_ticket(tickets[0]["ID"])
#         print(f"Found ticket TDx {ticket['ID']}")
#         return ticket


async def check_out_asset(
    tdx: tdxapi.TeamDynamixInstance,
    asset: dict[str, Any],
    ticket: dict[str, Any],
    owner: dict[str, Any],
    comment: Optional[str] = ""
) -> None:
    """Assign asset to person and attach to ticket.

    Args:
        tdx (tdxapi.TeamDynamixInstance): TeamDynamix Instance
        asset (dict): Asset to check out
        ticket (dict): Ticket to attach asset to
        person_uid (str): Person to assign asset to
    """
    tdx.attach_asset_to_ticket(ticket["ID"], asset["ID"])
    print(f"Attached asset to ticket {ticket['ID']}")
    loan_period: str = \
        tdx.get_ticket_attribute(ticket, "sah_Loan Length (Term)")["ValueText"]
    notes: str = (
        f"On Loan to {owner['AlternateID']} "
        f"in {ticket['ID']} until {loan_period}\n\n{comment}"
    )
    tdx.update_ticket_status(
        ticket["ID"], "Closed", notes
    )

    await inventory_asset(
        tdx,
        asset,
        "Offsite",
        "On Loan",
        owner["UID"],
        notes,
        update_inv_date=True
    )


async def check_in_asset(
    tdx: tdxapi.TeamDynamixInstance,
    asset: dict[str, Any],
    ticket: Optional[dict[str, Any]] = None
) -> None:
    """Check in a dropped off asset.

    Remove owner from asset,
    set In - Stock Reserved,
    set location to Michigan Union,
    attach asset to drop off ticket (if provided)

    Args:
        tdx (tdxapi.TeamDynamixInstance): TeamDynamix Instance
        asset (dict): Asset to check in
        ticket (dict): Ticket to attach asset to
    """
    if ticket:
        tdx.attach_asset_to_ticket(ticket["ID"], asset["ID"])
        print(f"Attached asset to ticket {ticket['ID']}")
        tdx.update_ticket_status(
            ticket["ID"], "Closed", "Checked in by Tech Consulting"
        )

    await inventory_asset(
        tdx,
        asset,
        "MICHIGAN UNION",
        "In Stock - Reserved",
        notes="Checked in by Tech Consulting",
    )
