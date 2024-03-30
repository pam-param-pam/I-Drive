#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class IDriveException(Exception):
    """A base class for I Drive exceptions."""

class ResourceNotFound(IDriveException):
    """Raised when resource can't be found in the database"""
    pass

class ResourcePermissionError(IDriveException):
    """Raised when user has not enough privilege to access a resource"""
    pass

class BadRequestError(IDriveException):
    """Raised when user request has some bad/missing data in it"""
    pass

class RootPermissionError(IDriveException):
    """Raised when user tries to manage 'root' folder"""
    pass
