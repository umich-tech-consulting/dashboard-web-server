"""Exceptions for dashboard-web-server."""


class MissingBodyException(Exception):
    """Missing body from request."""


class MalformedBodyException(Exception):
    """Body is missing required elements."""


class InvalidUniqnameException(Exception):
    """Uniqname is not 3-8 alpha characters."""


class InvalidAssetException(Exception):
    """Assets should start with TRL or SAH and 5 digits or SAHM and 4 digits"""
