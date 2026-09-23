from pathlib import Path
import json

SRC = Path("data/icon_v15_pine_reference.json")
OUT = Path("src/pine_libraries")
OUT.mkdir(parents=True, exist_ok=True)

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

data = json.loads(SRC.read_text())

for i, name in enumerate(ORDER):
    raw = data[name]
    # Support either a plain list or the current reference object's values field.
    vals = raw["values"] if isinstance(raw, dict) and "values" in raw else raw
    vals = sorted(float(x) for x in vals)
    unique = []
    counts = []
    for x in vals:
        if unique and x == unique[-1]:
            counts[-1] += 1
        else:
            unique.append(x)
            counts.append(1)

    values_text = ",".join(format(x, ".17g") for x in unique)
    counts_text = ",".join(str(x) for x in counts)
    title = f"IconV15_{i}"

    pine = f'''//@version=6
// Frozen Option 2A V15 reference: {name}
// Publish this library privately in TradingView. Do not edit the data.
library("{title}", overlay = false)

export rank(float x) =>
    var array<float> values = array.new_float()
    var array<int> counts = array.new_int()
    if array.size(values) == 0
        array<string> vs = str.split("{values_text}", ",")
        array<string> cs = str.split("{counts_text}", ",")
        for k = 0 to array.size(vs) - 1
            array.push(values, str.tonumber(array.get(vs, k)))
            array.push(counts, int(str.tonumber(array.get(cs, k))))
    int n = 1477
    int lo = 0
    int hi = array.size(values) - 1
    int pos = 0
    while lo <= hi
        int mid = int(math.floor((lo + hi) / 2))
        float mv = array.get(values, mid)
        if mv < x
            lo := mid + 1
        else
            pos := mid
            hi := mid - 1
    int below = 0
    if lo > 0
        for k = 0 to lo - 1
            below += array.get(counts, k)
    bool exact = lo < array.size(values) and array.get(values, lo) == x
    float r = exact ? below + (array.get(counts, lo) + 1.0) / 2.0 : below + 1.0
    math.min(math.max(r, 1.0), float(n)) / float(n)
'''
    p = OUT / f"{title}.pine"
    p.write_text(pine)
    print(f"{p}: {p.stat().st_size} bytes")

print("\nCreated 9 exact frozen V15 TradingView libraries.")
print("Next: publish each privately in TradingView as version 1.")
