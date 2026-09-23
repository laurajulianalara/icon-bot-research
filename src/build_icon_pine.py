import json
from pathlib import Path

REF = Path("data/icon_v15_pine_reference.json")
OUT = Path("src/icon_v15_reference_generated.pine")

if not REF.exists():
    raise SystemExit(f"Missing {REF}")

with REF.open() as f:
    refs = json.load(f)

ORDER = [
    "rejection_quality",
    "impulse_to_reclaim",
    "reclaim_to_sweep",
    "reversal_impulse",
    "reclaim_x_wick",
    "close_x_reclaim",
    "sweep_minus_reclaim",
    "impulse_minus_reclaim",
    "quality_balance",
]

def compress(values):
    """
    Convert sorted empirical distribution into:
      unique value
      count below value
      tie count

    This preserves the frozen pandas-style percentile rank:
        (below + (ties + 1) / 2) / N

    For a new value not exactly present:
        (below + 1) / N
    """
    vals = sorted(float(x) for x in values)
    n = len(vals)

    rows = []
    i = 0

    while i < n:
        value = vals[i]
        j = i + 1

        while j < n and vals[j] == value:
            j += 1

        rows.append((value, i, j - i))
        i = j

    return n, rows


def fmt(x):
    # 17 significant digits is enough to round-trip a Python float.
    return format(float(x), ".17g")


def pine_array_float(name, values):
    chunks = []

    for i in range(0, len(values), 100):
        part = ", ".join(fmt(x) for x in values[i:i+100])
        chunks.append(part)

    joined = ",\n    ".join(chunks)

    return (
        f"var array<float> {name} = array.from(\n"
        f"    {joined}\n"
        f")"
    )


def pine_array_int(name, values):
    chunks = []

    for i in range(0, len(values), 150):
        part = ", ".join(str(int(x)) for x in values[i:i+150])
        chunks.append(part)

    joined = ",\n    ".join(chunks)

    return (
        f"var array<int> {name} = array.from(\n"
        f"    {joined}\n"
        f")"
    )


lines = []

lines.append("// AUTO-GENERATED — DO NOT EDIT")
lines.append("// THE ICON — Frozen V15 empirical percentile reference")
lines.append("// Source: data/icon_v15_pine_reference.json")
lines.append("// Frozen population: 1,477 V11 rows")
lines.append("")

metadata = {}

for idx, col in enumerate(ORDER):
    n, rows = compress(refs[col])

    safe = f"v15_{idx}"

    values = [r[0] for r in rows]
    below  = [r[1] for r in rows]
    ties   = [r[2] for r in rows]

    metadata[col] = {
        "n": n,
        "unique": len(rows),
    }

    lines.append(f"// {col} | N={n} | UNIQUE={len(rows)}")
    lines.append(pine_array_float(f"{safe}_values", values))
    lines.append(pine_array_int(f"{safe}_below", below))
    lines.append(pine_array_int(f"{safe}_ties", ties))
    lines.append("")

lines.append("""
f_frozen_pct_rank(
    float x,
    array<float> values,
    array<int> below,
    array<int> ties,
    int n
) =>
    int sz = array.size(values)
    int lo = 0
    int hi = sz - 1
    int pos = sz

    while lo <= hi
        int mid = int(math.floor((lo + hi) / 2))
        float mv = array.get(values, mid)

        if mv >= x
            pos := mid
            hi := mid - 1
        else
            lo := mid + 1

    float rank = na

    if pos < sz and array.get(values, pos) == x
        int b = array.get(below, pos)
        int t = array.get(ties, pos)
        rank := (b + (t + 1.0) / 2.0) / n
    else
        int b = pos < sz ? array.get(below, pos) : n
        float ordinal = math.min(math.max(b + 1.0, 1.0), n)
        rank := ordinal / n

    rank
""".strip())

OUT.write_text("\n".join(lines) + "\n")

print("=== ICON V15 PINE REFERENCE BUILD ===")
print("SOURCE:", REF)
print("OUTPUT:", OUT)
print()

for col in ORDER:
    m = metadata[col]
    print(
        f"{col:25s} "
        f"N={m['n']:4d} "
        f"UNIQUE={m['unique']:4d}"
    )

print()
print("GENERATED SIZE:", OUT.stat().st_size, "bytes")
print("GENERATED LINES:", len(OUT.read_text().splitlines()))
print()
print("✅ Frozen V15 Pine reference generated.")
