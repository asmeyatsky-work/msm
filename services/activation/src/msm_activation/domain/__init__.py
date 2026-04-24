"""Activation domain. Pure decision rules (which channel, dedupe window, mode)."""
from .mode import ActivationMode
from .envelope import PredictionEnvelope

__all__ = ["ActivationMode", "PredictionEnvelope"]
