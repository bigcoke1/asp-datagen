"""Hold every generated bundle to the Evidence Bundle Schema page before anything labels it."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from datagen.contract import ATTRIBUTES

_SCHEMA = json.loads((Path(__file__).parent.parent / "schema" / "evidence-bundle.schema.json").read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA, format_checker=FormatChecker())


def problems(bundle: dict) -> list[str]:
    out = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in _VALIDATOR.iter_errors(bundle)]
    # Rule 5, which JSON Schema cannot express.
    ids = {a["id"] for a in bundle.get("attestations", [])}
    out += [f"attributes/{n}: attestation_ref {a['attestation_ref']} resolves to nothing"
            for n, a in bundle.get("attributes", {}).items() if "attestation_ref" in a and a["attestation_ref"] not in ids]
    # Rule 8: every name on the page is sent in every bundle.
    out += [f"attributes/{n}: missing" for n in ATTRIBUTES if n not in bundle.get("attributes", {})]
    return out
