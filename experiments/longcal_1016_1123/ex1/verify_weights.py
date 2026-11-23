"""Check native predictions and the binary model against the training implementation."""
import argparse
from pathlib import Path
import subprocess
import tempfile

import numpy as np

from train import forward, streams


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--model-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--work-root", type=Path, help="writable build directory for the native check")
    args = parser.parse_args()
    root = args.model_dir.resolve()
    weights = np.fromfile(root / "model.f32", dtype="<f4")
    if len(weights) != 37 or not np.isfinite(weights).all():
        raise ValueError("Expected exactly 37 finite weights")
    rng = np.random.default_rng(1123)
    features = rng.normal(size=(800, 5))
    features[:, 2] = np.abs(features[:, 2])
    features[:, 3] = rng.integers(0, 31, size=len(features))
    features[:12, 0] = 0
    features[12:22, 1] = 0
    current, history, support = streams(features)
    expected = support * forward(weights, current, history)[2]
    source = (
        '#include "candidate.hpp"\n#include <iostream>\n#include <iomanip>\n'
        'int main(){Candidate c; double d,h,s,v; int n; std::cout<<std::setprecision(17);'
        "while(std::cin>>d>>h>>s>>n>>v) std::cout<<c.predict(d,h,s,n,v)<<'\\n';}\n"
    )
    inputs = "\n".join(
        f"{d:.17g} {h:.17g} {s:.17g} {int(n)} {v:.17g}" for d, h, s, n, v in features
    )
    with tempfile.TemporaryDirectory(dir=args.work_root) as tmp:
        source_file = Path(tmp) / "probe.cpp"
        binary = Path(tmp) / "probe.exe"
        source_file.write_text(source, encoding="ascii")
        subprocess.run([args.compiler, "-std=c++17", "-O2", "-I", str(root),
                        str(source_file), "-o", str(binary)], check=True)
        result = subprocess.run([str(binary)], input=inputs, text=True, capture_output=True, check=True)
    actual = np.fromstring(result.stdout, sep=" ")
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-12)
    print(f"Native/Python parity across {len(actual)} cases: max error {abs(actual - expected).max():.3g} mm")


if __name__ == "__main__":
    main()
