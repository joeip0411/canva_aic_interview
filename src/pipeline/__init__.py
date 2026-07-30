"""Pipeline package — event validation, stream processing, and reporting."""

from src.pipeline.processor import Processor
from src.pipeline.schema import Event

__all__ = ["Event", "Processor"]
