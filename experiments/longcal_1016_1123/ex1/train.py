"""Fit two 4-unit streams on the shared, training-period-only V53 replay sample."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent


def streams(features):
    dev, hist, spread, count, velocity = features.T
    direction = np.sign(dev)
    current = np.column_stack([
        np.minimum(abs(dev), 2.0) / 0.8,
        np.clip(direction * velocity, -1.0, 1.0) / 0.3,
    ])
    history = np.column_stack([
        np.minimum(abs(hist), 2.0) / 0.8,
        np.minimum(spread, 2.0) / 0.8,
        np.minimum(count, 30) / 30,
    ])
    eligible = (count >= 2) & (direction * hist > 0)
    support = np.where(eligible, direction * np.minimum.reduce([
        np.abs(dev), np.abs(hist), np.full(len(dev), 0.8)]), 0.0)
    return current, history, support


def forward(p, local, recurring):
    current = np.maximum(local @ p[:8].reshape(2, 4) + p[8:12], 0.0)
    history = np.maximum(recurring @ p[12:24].reshape(3, 4) + p[24:28], 0.0)
    logit = current @ p[28:32] + history @ p[32:36] + p[36]
    gain = 1.0 / (1.0 + np.exp(-np.clip(logit, -30, 30)))
    return current, history, gain


def gradient(p, local, recurring, support, target, cfg):
    current, history, gain = forward(p, local, recurring)
    pred = support * gain
    delta = cfg["huber_delta_mm"]
    dpred = np.clip(pred - target, -delta, delta) + cfg["anchor_strength"] * pred
    dlogit = dpred * support * gain * (1.0 - gain) / len(pred)
    dcurrent = (dlogit[:, None] * p[28:32]) * (current > 0.0)
    dhistory = (dlogit[:, None] * p[32:36]) * (history > 0.0)
    grad = np.concatenate([
        (local.T @ dcurrent).ravel(), dcurrent.sum(axis=0),
        (recurring.T @ dhistory).ravel(), dhistory.sum(axis=0),
        current.T @ dlogit, history.T @ dlogit, [dlogit.sum()],
    ])
    grad += cfg["l2_strength"] * p
    return grad


def fit(features, targets, cfg):
    local, recurring, support = streams(features)
    label = support * np.maximum(0.0, 1.0 - features[:, 2] / (np.abs(features[:, 1]) + 0.1))
    if not np.allclose(targets, label, atol=1e-7, rtol=1e-6):
        raise ValueError("Training targets differ from the registered historical reliability proxy")
    eligible = support != 0
    if not eligible.any():
        raise ValueError("No training samples with nonzero sign-aligned historical support")
    idx = np.flatnonzero(eligible)
    rng = np.random.default_rng(cfg["seed"])
    if len(idx) > cfg["max_fit_examples"]:
        idx = np.sort(rng.choice(idx, size=cfg["max_fit_examples"], replace=False))
    p = rng.normal(0.0, 0.3, size=37)
    p[8:12] = 0.1
    p[24:28] = 0.1
    p[36] = 0.0
    first_moment = np.zeros_like(p)
    second_moment = np.zeros_like(p)
    step = 0
    for _ in range(cfg["epochs"]):
        order = rng.permutation(idx)
        for start in range(0, len(order), cfg["batch_size"]):
            batch = order[start:start + cfg["batch_size"]]
            grad = gradient(p, local[batch], recurring[batch], support[batch], targets[batch], cfg)
            step += 1
            first_moment = 0.9 * first_moment + 0.1 * grad
            second_moment = 0.999 * second_moment + 0.001 * grad**2
            m = first_moment / (1.0 - 0.9**step)
            v = second_moment / (1.0 - 0.999**step)
            p -= cfg["adam_learning_rate"] * m / (np.sqrt(v) + 1e-8)
    p = p.astype("<f4")
    _, _, gains = forward(p, local, recurring)
    pred = support * gains
    stats = {
        "finite_samples": len(targets), "nonzero_support_samples": len(np.flatnonzero(eligible)),
        "fit_examples": len(idx), "optimizer_steps": step,
        "all_training_proxy_mae_mm": float(np.mean(np.abs(pred - targets))),
        "zero_prediction_proxy_mae_mm": float(np.mean(np.abs(targets))),
        "mean_abs_prediction_mm": float(np.mean(np.abs(pred))),
        "nonzero_support_mean_gain": float(gains[eligible].mean()),
    }
    return p, stats


def export_weights(p, directory):
    directory.mkdir(parents=True, exist_ok=True)
    blob = p.astype("<f4").tobytes()
    (directory / "model.f32").write_bytes(blob)
    # Nine significant decimal digits round-trip all finite float32 values.
    constants = [format(float(w), ".8e") + "f" for w in p]
    lines = ["    " + ", ".join(constants[i:i+4]) + "," for i in range(0, 37, 4)]
    header = ("#pragma once\nnamespace dual_stream_weights {\n"
              "inline constexpr float p[37] = {\n" + "\n".join(lines) + "\n};\n}\n")
    (directory / "weights.hpp").write_text(header, encoding="ascii")
    return sha256(blob).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    with np.load(args.samples, allow_pickle=False) as data:
        features = np.asarray(data["features"], dtype=np.float64)
        targets = np.asarray(data["target"], dtype=np.float64)
    if features.ndim != 2 or features.shape != (len(targets), 5) or targets.ndim != 1:
        raise ValueError("Expected N x 5 features and length-N targets")
    valid = (np.isfinite(features).all(axis=1) & np.isfinite(targets)
             & (features[:, 2] >= 0) & (features[:, 3] >= 0))
    p, stats = fit(features[valid], targets[valid], cfg)
    stats["invalid_samples"] = int((~valid).sum())
    stats["training_npz_sha256"] = sha256(args.samples.read_bytes()).hexdigest()
    stats["parameters"] = len(p)
    stats["model_bytes"] = p.nbytes
    stats["model_sha256"] = export_weights(p, args.out)
    (args.out / "fit_report.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
