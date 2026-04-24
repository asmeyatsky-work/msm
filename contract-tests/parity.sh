#!/usr/bin/env bash
# Cross-language wire parity: encode a message with Rust, decode with Python.
# Run from repo root. Requires: cargo, protoc, python3 with grpcio-tools.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/contract-tests/.out"
rm -rf "$OUT" && mkdir -p "$OUT"

# 1. Python codegen from the canonical proto (isolated venv; PEP 668-safe).
VENV="$OUT/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet grpcio-tools protobuf
"$VENV/bin/python" -m grpc_tools.protoc \
  -I"$ROOT/proto" \
  --python_out="$OUT" \
  "$ROOT/proto/scoring.proto"

# 2. Rust encodes a sample message, prints hex to stdout.
HEX=$(cd "$ROOT/services/scoring-api" && cargo run --quiet -p msm-scoring-contract \
  --example encode_sample 2>/dev/null)

# 3. Python decodes the hex and asserts field values.
"$VENV/bin/python" - <<PY
import sys, binascii
sys.path.insert(0, "$OUT")
import scoring_pb2 as pb

raw = binascii.unhexlify("$HEX")
msg = pb.ScoreRequest.FromString(raw)
assert msg.features.click_id == "c-rt", msg.features.click_id
assert abs(msg.features.cerberus_score - 0.8) < 1e-9
print("parity OK")
PY
