"""
Verification module: FEMM 4.2 FEA cross-verification tools.
"""

from .femm_runner import run_femm_simulation, FEMMResult, VerificationRow

__all__ = ["run_femm_simulation", "FEMMResult", "VerificationRow"]
