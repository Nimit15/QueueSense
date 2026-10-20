import csv
import math
import sys
from pathlib import Path

RESULTS_DIR = Path(r"D:\QueueSense\results\network_v2_diagnostics")
PATTERN_PREFIXES = ["A", "B", "C", "D1", "D2"]
SCENARIOS = ["light", "balanced", "uneven", "bottleneck", "surge"]

REQUIRED_COLUMNS = [
    "time",
    "arrived_this_step",
    "arrived_cumulative",
    "remaining_expected",
    "queue_ns",
    "queue_ew",
    "spillback_ns",
    "spillback_ew",
    "downstream_occupancy",
    "spillback_threshold",
    "spillback_gate",
]

BOOL_COLS = {"spillback_gate"}

def validate_file(fp):
    errors = []
    try:
        with open(fp, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except Exception as e:
        return False, [f"Cannot read file: {e}"]
    if not rows:
        return False, ["Empty file"]
    header = [h.strip() for h in rows[0]]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        errors.append(f"Missing columns: {missing}")
    col_idx = {c:i for i,c in enumerate(header)}
    data_rows = rows[1:]
    if len(data_rows) != 241:
        errors.append(f"Expected 241 data rows, got {len(data_rows)}")
    prev_time = None
    prev_cum = None
    last_time = None
    for i, row in enumerate(data_rows, start=2):
        if len(row) < len(header):
            errors.append(f"Row {i} short")
            continue
        # time
        if "time" in col_idx:
            try:
                t = float(row[col_idx["time"]])
            except:
                errors.append(f"Row {i} time not numeric")
                t = None
            else:
                if prev_time is not None and t <= prev_time:
                    errors.append(f"Row {i} time not monotonic ({prev_time} -> {t})")
                prev_time = t
                last_time = t
        # arrived_cumulative
        if "arrived_cumulative" in col_idx:
            try:
                cum = float(row[col_idx["arrived_cumulative"]])
            except:
                errors.append(f"Row {i} arrived_cumulative not numeric")
                cum = None
            else:
                if prev_cum is not None and cum < prev_cum - 1e-9:
                    errors.append(f"Row {i} arrived_cumulative decreased ({prev_cum} -> {cum})")
                if math.isnan(cum) or math.isinf(cum):
                    errors.append(f"Row {i} arrived_cumulative NaN/inf")
                prev_cum = cum
        # downstream_occupancy
        if "downstream_occupancy" in col_idx:
            val = row[col_idx["downstream_occupancy"]].strip()
            if val == "":
                continue
            try:
                occ = float(val)
            except:
                errors.append(f"Row {i} downstream_occupancy not numeric")
            else:
                if math.isnan(occ) or math.isinf(occ):
                    errors.append(f"Row {i} downstream_occupancy NaN/inf")
                elif not (0.0 <= occ <= 1.0):
                    errors.append(f"Row {i} downstream_occupancy out of [0,1]: {occ}")
        # other columns
        for c in REQUIRED_COLUMNS:
            if c not in col_idx:
                continue
            if c in BOOL_COLS:
                v = row[col_idx[c]].strip()
                if v not in ("True", "False", "1", "0", ""):
                    errors.append(f"Row {i} {c} not boolean")
                continue
            if c == "downstream_occupancy":
                continue
            v = row[col_idx[c]].strip()
            if v == "":
                errors.append(f"Row {i} {c} empty")
                continue
            try:
                f = float(v)
            except:
                errors.append(f"Row {i} {c} not numeric")
                continue
            if math.isnan(f) or math.isinf(f):
                errors.append(f"Row {i} {c} NaN/inf")
    if last_time is not None and abs(last_time - 300.0) > 1e-6:
        errors.append(f"Last time != 300.0, got {last_time}")
    # spillback threshold for D1/D2
    controller = fp.stem.split("_")[0]
    if controller in ("D1", "D2") and "spillback_threshold" in col_idx:
        for i, row in enumerate(data_rows, start=2):
            try:
                th = float(row[col_idx["spillback_threshold"]])
            except:
                errors.append(f"Row {i} spillback_threshold not numeric")
                continue
            if abs(th - 0.3) > 1e-9:
                errors.append(f"Row {i} spillback_threshold !=0.3, got {th}")
    # deduplicate
    seen=set()
    uniq=[]
    for e in errors:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    passed = len(uniq)==0
    return passed, uniq

def main():
    results=[]
    for ctrl in PATTERN_PREFIXES:
        for scen in SCENARIOS:
            name = f"{ctrl}_seed42_{scen}_seed42.csv"
            fp = RESULTS_DIR / name
            if not fp.exists():
                results.append((name, False, [f"File not found"]))
                continue
            passed, errs = validate_file(fp)
            results.append((name, passed, errs))
    for name, passed, errs in results:
        status="PASS" if passed else "FAIL"
        print(f"{name}: {status}")
        for e in errs[:10]:
            print(f"  - {e}")
        if len(errs)>10:
            print(f"  ... {len(errs)-10} more")
    total=len(results)
    passed_cnt=sum(1 for _,p,_ in results if p)
    print(f"\nSummary: {passed_cnt}/{total} passed")
    sys.exit(0 if passed_cnt==total else 1)

if __name__=="__main__":
    main()
