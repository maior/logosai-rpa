"""LogosRPA — Desktop RPA for AI agents."""

__version__ = "0.1.0"

from .rpa import RPA
from .screen import Screen, ScreenElement
from .browser import Browser

__all__ = ["RPA", "Screen", "ScreenElement", "Browser"]
