"""Useful functions for managing consulting loaners.

Returns:
    _type_: _description_
"""

from datetime import date
from typing import Any, Optional

import tdxapi


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
    assets = await tdx.search_assets(asset_tag)
    if len(assets) == 0:
        raise tdxapi.ObjectNotFoundException
    elif len(assets) > 1:
        asset = _multiple_matches_chooser(assets, "Tag")
        deep_asset = await tdx.get_asset(asset["ID"])
        return deep_asset
    else:
        asset = await tdx.get_asset(assets[0]["ID"])
        print(f"Found asset {asset_tag}")
        return asset


# def find_person_uid(tdx: tdxapi.TeamDynamixInstance, uniqname: str) -> str:
#     """Find the UID of a person in TDx based on uniqname.

#     Args:
#         tdx (tdxapi.TeamDynamixInstance): _description_
#         uniqname (str): _description_

#     Returns:
#         str: _description_
#     """
#     print(f"Searching for person with uniqname {uniqname}")
#     people = tdx.search_people(uniqname)
#     if len(people) == 0:
#         exit(f"No people with uniqname {uniqname} found, aborting...")
#     elif len(people) > 1:
#         person = _multiple_matches_chooser(people, "PrimaryEmail")
#         return person["UID"]
#     else:
#        print(f"Found person with uniqname {uniqname}")
#        person_uid = people[0]["UID"]
#        return person_uid


def find_sah_request_ticket(
    tdx: tdxapi.TeamDynamixInstance, person_uid: str
) -> dict[str, Any]:
    """Find a ticket assigned to ITS-Sitesathome with title Sites@Home Request.

    Args:
        tdx (tdxapi.TeamDynamixInstance): TeamDynamix instance
        person_uid (str): UID of person in TeamDynamix

    Returns:
        dict: Latest matching ticket
    """
    print("Searching for Sites@Home request tickets")
    tickets = tdx.search_tickets(
        person_uid,
        ["Open", "Scheduled", "Closed"],
        "Sites @ Home Request",
        "ITS-SitesatHome",
    )
    if len(tickets) == 0:
        exit("No matching tickets found, aborting...")

    elif len(tickets) > 1:
        ticket = _multiple_matches_chooser(tickets, "ID")
        return tdx.get_ticket(ticket["ID"])
    else:
        ticket = tdx.get_ticket(tickets[0]["ID"])
        print(f"Found ticket TDx {ticket['ID']}")
        return ticket


def find_sah_drop_off_ticket(
    tdx: tdxapi.TeamDynamixInstance, person_uid: str
) -> dict[str, Any]:
    """Find return request for Sites at Home laptop.

    Find a ticket assigned to ITS-SitesatHome with title\
    IMPORTANT: Sites@Home Laptop Return or Extension.

    Args:
        tdx (tdxapi.TeamDynamixInstance): _description_
        person_uid (str): _description_

    Returns:
        dict: _description_
    """
    print("Searching for Sites@Home return tickets")
    tickets = tdx.search_tickets(
        person_uid,
        [
            "New",
            "Open",
            "Scheduled",
        ],
        "IMPORTANT: Sites@Home Laptop Return or Extension",
        "ITS-SitesatHome",
    )
    if len(tickets) == 0:
        raise tdxapi.ObjectNotFoundException
    elif len(tickets) > 1:
        ticket = _multiple_matches_chooser(tickets, "ID")
        return ticket
    else:
        ticket = tdx.get_ticket(tickets[0]["ID"])
        print(f"Found ticket TDx {ticket['ID']}")
        return ticket


async def check_out_asset(
    tdx: tdxapi.TeamDynamixInstance,
    asset: dict[str, Any],
    ticket: dict[str, Any],
    person_uid: str
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
    loan_period = tdx.get_ticket_attribute(ticket, "sah_Loan Length (Term)")[
        "ValueText"
    ]
    tdx.update_ticket_status(
        ticket["ID"], "Closed", "Checked out by Tech Consulting"
    )

    await inventory_asset(
        tdx,
        asset,
        "Offsite",
        "On Loan",
        person_uid,
        f"On Loan until {loan_period}"
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


def _multiple_matches_chooser(
    matches: list[Any],
    primary_key: Optional[str] = None
) -> Any:
    """Interactively choose a single object from a list.

    Args:
        matches (list[Any]): List of objects to choose from
        primary_key (Optional[str]): Identifier to print if objects are dicts

    Returns:
        Any: The object that was selected
    """
    if len(matches) > 10:
        print(f"Found {len(matches)} matches (max 10), aborting...")
        exit()
    else:
        print(f"Found {len(matches)} matches, choose one to use:")
    if primary_key:
        i = 1
        for obj in matches:
            print(f"\t{i}: {obj[primary_key]}")
            i += 1
    else:
        i = 1
        for obj in matches:
            print(f"\t{i}: {obj[0]}")
            i += 1
    choice = -1
    while choice not in range(1, len(matches) + 1):
        choice = int(input("Select an option: "))
        if choice not in range(1, len(matches) + 1):
            print(f"Invalid entry, select between 1 and {len(matches)}")
    return matches[choice - 1]
