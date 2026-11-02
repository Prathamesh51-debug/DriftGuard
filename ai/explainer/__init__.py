"""Explainer: plain-English explanation of a Result, with every figure checked against the Result."""

from .explainer import Explanation, explain, template_explanation
from .verify import verify_text

__all__ = ["Explanation", "explain", "template_explanation", "verify_text"]
