"""Rebuild the three-night ablation from ex1; verify an assembled checkout without ex1."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import struct


HERE = Path(__file__).resolve().parent
WINDOW = b"static constexpr int history_days = 30;"


def canonical(data):
    return data.replace(b"\r\n", b"\n")


def digest(data):
    return sha256(data).hexdigest()


def json_bytes(item):
    return (json.dumps(item, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def check_weights(header, model, fit):
    body = re.search(rb"\bp\[37\]\s*=\s*\{([^}]+)\}", header)
    if not body:
        raise ValueError("Missing constexpr float p[37] in weights.hpp")
    fields = [x.strip() for x in body[1].split(b",") if x.strip()]
    if len(fields) != 37 or any(not field.endswith(b"f") for field in fields):
        raise ValueError("Expected 37 float literals in weights.hpp")
    values = [float(field[:-1]) for field in fields]
    if not all(map(math.isfinite, values)) or struct.pack("<37f", *values) != model:
        raise ValueError("C++ literals differ from the 148-byte binary model")
    if fit["parameters"] != 37 or fit["model_bytes"] != 148 or fit["model_sha256"] != digest(model):
        raise ValueError("Source fit manifest does not match the supplied model")


def assemble(source, output):
    original = (source / "candidate.hpp").read_bytes()
    if original.count(WINDOW) != 1:
        raise ValueError("Expected one ex1 history_days = 30 declaration")
    candidate = original.replace(WINDOW, WINDOW.replace(b"30", b"3"))
    config = json.loads((source / "config.json").read_bytes())
    if config["history_days"] != 30:
        raise ValueError("Unexpected ex1 history configuration")
    control = dict(config, history_days=3)
    weights = (source / "weights.hpp").read_bytes()
    model = (source / "model.f32").read_bytes()
    fit = json.loads((source / "fit_report.json").read_bytes())
    check_weights(weights, model, fit)
    manifest = {
        "history_days_ex1": 30, "history_days_ex4": 3,
        "ex1_candidate_text_sha256": digest(canonical(original)),
        "ex4_candidate_text_sha256": digest(canonical(candidate)),
        "ex1_config_sha256": digest(json_bytes(config)),
        "shared_weight_header_text_sha256": digest(canonical(weights)),
        "shared_model_bytes": len(model), "shared_model_sha256": digest(model),
        "ex1_fit_report_sha256": digest(json_bytes(fit)),
    }
    for name, data in (("candidate.hpp", candidate), ("config.json", json_bytes(control)),
                       ("weights.hpp", weights), ("model.f32", model),
                       ("ex1_fit_report.json", json_bytes(fit)),
                       ("ablation_manifest.json", json_bytes(manifest))):
        (output / name).write_bytes(data)


def verify(output):
    manifest = json.loads((output / "ablation_manifest.json").read_bytes())
    candidate = canonical((output / "candidate.hpp").read_bytes())
    short = WINDOW.replace(b"30", b"3")
    if candidate.count(short) != 1 or digest(candidate) != manifest["ex4_candidate_text_sha256"]:
        raise ValueError("Three-night candidate hash mismatch")
    if digest(candidate.replace(short, WINDOW)) != manifest["ex1_candidate_text_sha256"]:
        raise ValueError("Restoring the 30-night window does not reproduce the ex1 source")
    config = json.loads((output / "config.json").read_bytes())
    if config["history_days"] != 3 or digest(json_bytes(dict(config, history_days=30))) != manifest["ex1_config_sha256"]:
        raise ValueError("Configuration differs beyond the declared history length")
    header = canonical((output / "weights.hpp").read_bytes())
    model = (output / "model.f32").read_bytes()
    fit = json.loads((output / "ex1_fit_report.json").read_bytes())
    check_weights(header, model, fit)
    if (digest(header) != manifest["shared_weight_header_text_sha256"] or
            digest(model) != manifest["shared_model_sha256"] or
            digest(json_bytes(fit)) != manifest["ex1_fit_report_sha256"]):
        raise ValueError("Frozen weights or source fit report changed")
    print(f"Verified identical 37 FP32 weights ({len(model)} bytes), SHA-256 {digest(model)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ex1", type=Path, help="assemble from this fitted ex1 checkout before verification")
    p.add_argument("--out", type=Path, default=HERE)
    args = p.parse_args()
    if args.ex1:
        if args.ex1.resolve() == args.out.resolve():
            p.error("ex1 source and output directories must differ")
        args.out.mkdir(parents=True, exist_ok=True)
        assemble(args.ex1, args.out)
    verify(args.out)
