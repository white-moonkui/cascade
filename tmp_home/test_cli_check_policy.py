"""Test cascade check --policy."""
import os
import sys
import tempfile

os.environ["USERPROFILE"] = "D:\\cascade\\tmp_home"

sys.argv = [
    "cascade",
    "check",
    "--tool-calls", '[{"id":"1","name":"search","confidence":0.9}]',
    "--policy", os.path.join(os.path.dirname(__file__), "..", "tests", "policies", "strict.yaml"),
]
from cascade.cli import main
main()
