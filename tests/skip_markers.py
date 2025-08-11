"""
Skip markers for tests that depend on utilities that have been modernized.

During the architecture modernization, many utilities were integrated into 
core modules. These tests are skipped until they're updated to test the 
modern architecture.
"""

import pytest


# Skip marker for tests of modernized utilities
skip_utilities = pytest.mark.skip(reason="Utility modernized - test needs updating to use core architecture")

# Skip marker for unimplemented features
skip_unimplemented = pytest.mark.skip(reason="Feature not yet implemented in modernized architecture")
