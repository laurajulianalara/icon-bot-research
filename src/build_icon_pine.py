import json
from pathlib import Path

REF = Path("data/icon_v15_pine_reference.json")
OUT = Path("src/icon_v15_reference_generated.pine")

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

refs = json.loads(REF.read_text())


def compress(values):
    vals = sorted(float(x) for x in values)
    rows = []

    i = 0
    while i < len(vals):
        value = vals[i]
        j = i + 1

        while j < len(vals) and vals[j] == value:
            j += 1

        rows.append((value, j - i))
        i = j

    return len(vals), rows


def fmt(x):
    # Preserve round-trip Python float precision.
    return format(float(x), ".17g")


lines = [
    "// AUTO-GENERATED — DO NOT EDIT",
    "// THE ICON — Compact Frozen V15 empirical reference",
    "// Full precision values preserved.",
    "// Counts reconstruct frozen tie/below behavior.",
    "",
]

metadata = {}

for idx, col in enumerate(ORDER):
    n, rows = compress(refs[col])

    values = ",".join(fmt(v) for v, _ in rows)
    counts = ",".join(str(c) for _, c in rows)

    metadata[col] = {
        "n": n,
        "unique": len(rows),
    }

    # Store the distribution as text rather than thousands of Pine
    # syntax-tree array elements. Pine reconstructs the arrays once.
    lines += [
        f'var string v15_{idx}_values_text = "{values}"',
        f'var string v15_{idx}_counts_text = "{counts}"',
        f"var array<float> v15_{idx}_values = array.new_float()",
        f"var array<int> v15_{idx}_counts = array.new_int()",
        "",
    ]


lines.append("""
f_load_frozen_ref(
    string valuesText,
    string countsText,
    array<float> values,
    array<int> counts
) =>
    if array.size(values) == 0
        array<string> vs = str.split(valuesText, ",")
        array<string> cs = str.split(countsText, ",")

        int sz = array.size(vs)

        if sz > 0
            for i = 0 to sz - 1
                float v = str.tonumber(array.get(vs, i))
                int c = int(str.tonumber(array.get(cs, i)))

                array.push(values, v)
                array.push(counts, c)
""".strip())

lines.append("")

# Load once on the first chart bar.
lines.append("if barstate.isfirst")

for idx in range(len(ORDER)):
    lines.append(
        f"    f_load_frozen_ref("
        f"v15_{idx}_values_text, "
        f"v15_{idx}_counts_text, "
        f"v15_{idx}_values, "
        f"v15_{idx}_counts)"
    )

lines.append("")

lines.append("""
f_frozen_pct_rank(
    float x,
    array<float> values,
    array<int> counts,
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

    int below = 0

    if pos > 0
        for k = 0 to pos - 1
            below += array.get(counts, k)

    float rank = na

    if pos < sz and array.get(values, pos) == x
        int ties = array.get(counts, pos)
        rank := (below + (ties + 1.0) / 2.0) / n
    else
        float ordinal = math.min(
            math.max(below + 1.0, 1.0),
            n
        )
        rank := ordinal / n

    rank
""".strip())

OUT.write_text("\n".join(lines) + "\n")

print("=== ICON V15 COMPACT PINE BUILD ===")
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
print("✅ Compact frozen V15 reference generated.")
