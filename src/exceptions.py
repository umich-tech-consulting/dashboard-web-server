"""Exceptions for dashboard-web-server."""


class MissingBodyException(Exception):
    """Missing body from request."""


class MalformedBodyException(Exception):
    """Body is missing required elements."""


class InvalidUniqnameException(Exception):
    """Uniqname is not 3-8 alpha characters."""

    def __init__(
            self,
            uniqname: str,
            message: str = "Uniqname must be 3-8 alpha characters"
    ) -> None:
        self.message: str = message
        self.uniqname: str = uniqname
        super().__init__(self.message)


class InvalidAssetException(Exception):
    """Assets start with TRL/SAH and 5 digits or SAHM and 4 digits."""

    def __init__(
            self,
            asset: str,
            message: str = 
            "Asset are TRL/SAH and 5 digits, or SAHM and 4 digits"
    ) -> None:
        self.asset: str = asset
        self.message: str = message
        super().__init__(self.message)


class AssetNotFoundException(Exception):
    """Asset does not exist in TDx."""

    def __init__(
            self,
            asset: str,
            message: str = "Asset was not found in TDx"
    ) -> None:
        self.asset: str = asset
        self.message: str = message
        super().__init__(self.message)


class NoLoanRequestException(Exception):
    """No loan request in TDx."""

    def __init__(
            self,
            uniqname: str,
            message: str = "No loan ticket in TDx"
    ) -> None:
        self.uniqname: str = uniqname
        self.message: str = message
        super().__init__(self.message)


class AssetNotReadyToLoanException(Exception):
    """Asset is not in stock available."""

    def __init__(
            self,
            asset: str,
            message: str = "Asset not ready to loan"
    ):
        self.asset: str = asset
        self.message: str = message
        super().__init__(self.message)


class AssetAlreadyCheckedInException(Exception):
    """Asset is not in stock available."""

    def __init__(
            self,
            asset: str,
            message: str = "Asset already available"
    ):
        self.asset: str = asset
        self.message: str = message
        super().__init__(self.message)


class TDXCommunicationException(Exception):
    """Error communicating with TDx."""

    def __init__(
            self,
            message: str = "Could not connect to TDx"
    ):
        self.message: str = message
        super().__init__(self.message)


class LoanAlreadyFulfilledException(Exception):
    """Ticket already has asset attached (loan already completed)."""

    def __init__(
            self,
            ticket: str,
            asset: str,
            message: str = "Loan already fulfilled"
    ):
        self.ticket = ticket
        self.asset = asset
        self.message = message

        super().__init__(self.message)
