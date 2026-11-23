"""Republish the four-night Y extract from the project SQLite snapshots, read-only."""

from __future__ import annotations

import argparse
import csv
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


TZ = timezone(timedelta(hours=8))
NIGHTS = ("2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22")
DEVICES = {
    "left": ("780630499846", "780637798298", "780638271319",
             "780638310097", "780638327479", "780638349768"),
    "right": ("780639173835", "780639298317", "780639333715",
              "780639346578", "780639376393", "780639414923"),
}
MARKERS_PER_LINE = {"left": 191, "right": 200}
CAMERA_PER_LINE = {"left": 254, "right": 268}
# The point and node outputs at this rollover timestamp were written in the next file.
ROLLOVER = 1795214885202
# The first of two left-line input frames in this clock minute has no output rows.
INPUT_ONLY = 1795377727155
REPLAY_DEVICE = "780638271319"
REPLAY_START = 1795083152141

ROOT = Path(__file__).resolve().parents[1]


def stamp(night, hour=22):
    return int(datetime.fromisoformat(night).replace(hour=hour, tzinfo=TZ).timestamp() * 1000)


def local_time(ts):
    return datetime.fromtimestamp(ts / 1000, tz=TZ).isoformat(timespec="milliseconds")


def paths_for(root):
    return {
        "left": [root / "左线" / "NewDevice" / f"1793507670403_DataBaseFile_{n}.db"
                 for n in (12, 13, 14)],
        "right": [root / "右线" / f"1794993981365_DataBaseFile_{n}.db"
                  for n in (1, 2, 3)],
    }


def connect(path):
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return closing(conn)


def camera_rows(paths):
    pieces = []
    for line, files in paths.items():
        for path in files:
            status = path.stat()
            with connect(path) as conn:
                for device in DEVICES[line]:
                    table = f"Marker_{device}"
                    clause = (f'FROM "{table}" INDEXED BY "idx_{table}_timestamp" '
                              "WHERE timestamp>=? AND timestamp<?")
                    for night in NIGHTS:
                        start = stamp(night)
                        bounds = (start, start + 36_000_000)
                        rows = pd.read_sql_query(
                            f"SELECT timestamp,markerName,RoiCalState,scale,centerX,centerY,y,calY {clause}",
                            conn, params=bounds)
                        expected = conn.execute(f"SELECT count(*) {clause}", bounds).fetchone()[0]
                        assert len(rows) == expected
                        if len(rows):
                            pieces.append(rows.assign(night=night, line=line, device=device, part=path.name))
            after = path.stat()
            assert (status.st_size, status.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    camera = pd.concat(pieces, ignore_index=True)
    assert len(camera) == 1_253_054
    assert not camera.duplicated(["line", "timestamp", "device", "markerName"]).any()
    assert camera.RoiCalState.isin([0, 1]).all()
    assert np.isfinite(camera.scale).all() and camera.scale.gt(0).all()
    return camera


def read_partition_points(conn, desired, points_per_frame):
    collected = []
    wanted = set(desired.timestamp)
    counts = {}
    for start in range(1, 1_000_002, 20_000):
        rows = pd.read_sql_query(
            """SELECT timestamp,markerName,y0 FROM MarkerData NOT INDEXED
               WHERE rowid>=? AND rowid<?""", conn, params=(start, start + 20_000))
        if rows.empty:
            break
        accepted = rows[rows.timestamp.isin(wanted)]
        if len(accepted):
            collected.append(accepted)
            for ts, count in accepted.groupby("timestamp").size().items():
                counts[ts] = counts.get(ts, 0) + count
        complete = len(counts) == len(wanted) and min(counts.values()) >= points_per_frame
        if complete or rows.timestamp.min() > max(wanted):
            break
    return pd.concat(collected, ignore_index=True).merge(desired, on="timestamp", validate="many_to_one")


def downstream_rows(paths, camera):
    frames = camera[["line", "part", "night", "timestamp"]].drop_duplicates()
    all_points, all_nodes = [], []
    for line, files in paths.items():
        for path in files:
            expected = frames[frames.line.eq(line) & frames.part.eq(path.name)][["timestamp", "night"]].copy()
            if line == "left":
                expected = expected[~expected.timestamp.isin([ROLLOVER, INPUT_ONLY])]
                if path.name.endswith("_13.db"):
                    continuation = pd.DataFrame({"timestamp": [ROLLOVER], "night": ["2026-11-20"]})
                    expected = pd.concat([expected, continuation], ignore_index=True)
            with connect(path) as conn:
                points = read_partition_points(conn, expected, MARKERS_PER_LINE[line])
                nodes = pd.read_sql_query("SELECT timestamp,deviceId,y0 FROM SubDeviceDisData", conn)
                nodes = nodes.merge(expected, on="timestamp", validate="many_to_one")
            assert points.groupby("timestamp").size().eq(MARKERS_PER_LINE[line]).all()
            assert nodes.groupby("timestamp").size().eq(6).all()
            assert set(points.timestamp) == set(nodes.timestamp) == set(expected.timestamp)
            all_points.append(points.assign(line=line))
            all_nodes.append(nodes.assign(line=line))
    points = pd.concat(all_points, ignore_index=True)
    nodes = pd.concat(all_nodes, ignore_index=True)
    for data, key, count in ((points, "markerName", 938_400), (nodes, "deviceId", 28_800)):
        assert len(data) == count and np.isfinite(data.y0).all()
        assert not data.duplicated(["line", "timestamp", key]).any()
        assert data.groupby(["line", "night"]).timestamp.nunique().eq(600).all()
    return points, nodes


def export_table(path, table):
    path.parent.mkdir(exist_ok=True, parents=True)
    table.to_csv(path, index=False, lineterminator="\n", float_format="%.7f")


def export_dataset(root, camera, markers, nodes):
    ids = camera[["line", "device", "markerName"]].drop_duplicates().sort_values(
        ["line", "device", "markerName"]).reset_index(drop=True)
    ids.insert(0, "channel_id", ids.index + 1)
    names = markers[["line", "markerName"]].drop_duplicates().sort_values(
        ["line", "markerName"]).reset_index(drop=True)
    names.insert(0, "point_id", names.index + 1)
    device_ids = ids[["line", "device"]].drop_duplicates().sort_values(["line", "device"]).reset_index(drop=True)
    device_ids.insert(0, "node_id", device_ids.index + 1)
    export_table(root / "channels.csv", ids.rename(columns={"device": "device_id", "markerName": "marker_name"}))
    export_table(root / "markers.csv", names.rename(columns={"markerName": "marker_name"}))
    export_table(root / "devices.csv", device_ids.rename(columns={"device": "device_id"}))
    assert len(ids) == 522 and len(names) == 391 and len(device_ids) == 12

    camera = camera.merge(ids, on=["line", "device", "markerName"], validate="many_to_one")
    meta_keys = ["night", "channel_id"]
    meta = camera[meta_keys + ["scale", "centerX", "centerY"]].drop_duplicates()
    assert not meta.duplicated(meta_keys).any()
    # Preserve calibration precision in the small metadata file.
    meta = meta.sort_values(meta_keys).rename(columns={
        "scale": "scale_px_per_mm", "centerX": "center_x_px", "centerY": "center_y_px"})
    meta.to_csv(root / "calibration.csv", index=False, lineterminator="\n", float_format="%.17g")
    assert len(meta) == 2_088

    markers = markers.merge(names, on=["line", "markerName"], validate="many_to_one")
    nodes = nodes.merge(device_ids.rename(columns={"device": "deviceId"}),
                        on=["line", "deviceId"], validate="many_to_one")
    results = []
    for night in NIGHTS:
        for line in DEVICES:
            c = camera[camera.night.eq(night) & camera.line.eq(line)]
            p = markers[markers.night.eq(night) & markers.line.eq(line)]
            n = nodes[nodes.night.eq(night) & nodes.line.eq(line)]
            frames = c[["timestamp", "part"]].drop_duplicates().sort_values("timestamp").reset_index(drop=True)
            assert frames.timestamp.is_unique
            frames.insert(0, "frame_id", frames.index)
            frames["local_time"] = frames.timestamp.map(local_time)
            frames["has_y0"] = frames.timestamp.isin(p.timestamp).astype(int)
            assert c.groupby("timestamp").size().eq(CAMERA_PER_LINE[line]).all()
            base = root / night / line
            export_table(base / "frames.csv", frames.rename(columns={"timestamp": "timestamp_ms", "part": "camera_partition"}))
            compact = c.merge(frames[["timestamp", "frame_id"]], on="timestamp", validate="many_to_one")
            compact = compact.rename(columns={"RoiCalState": "roi", "y": "y_mm", "calY": "cal_y_mm"})
            cols = ["frame_id", "channel_id", "roi", "y_mm", "cal_y_mm"]
            export_table(base / "camera_y.csv", compact[cols].sort_values(cols[:2]))
            for filename, q, key in (("marker_y0.csv", p, "point_id"), ("node_y0.csv", n, "node_id")):
                aligned = q.merge(frames[["timestamp", "frame_id"]], on="timestamp", validate="many_to_one")
                assert len(aligned) == len(q)
                cols = ["frame_id", key, "y0_mm"]
                export_table(base / filename, aligned.rename(columns={"y0": "y0_mm"})[cols].sort_values(cols[:2]))
            results.append({
                "night": night, "line": line, "camera_frames": len(frames), "camera_rows": len(c),
                "y0_frames": int(frames.has_y0.sum()), "marker_y0_rows": len(p), "node_y0_rows": len(n),
            })
    return results


def export_replay(root, left_paths, state):
    replay = root / "replay_zd1403"
    replay.mkdir(exist_ok=True)
    night_end = stamp("2026-11-23", 8)
    table = f"Marker_{REPLAY_DEVICE}"
    pieces = []
    for path in left_paths:
        with connect(path) as conn:
            pieces.append(pd.read_sql_query(
                f"""SELECT timestamp,markerName,RoiCalState,x,y,calY FROM {table}
                    WHERE timestamp>? AND timestamp<?""", conn, params=(REPLAY_START, night_end)))
    raw = pd.concat(pieces, ignore_index=True).sort_values(["timestamp", "markerName"])
    assert len(raw) == 5_148 * 34
    assert not raw.duplicated(["timestamp", "markerName"]).any()
    cols = {"timestamp": "timestamp_ms", "markerName": "marker_name", "RoiCalState": "roi",
            "x": "x_mm", "y": "y_mm", "calY": "cal_y_mm"}
    raw.rename(columns=cols).to_csv(replay / "device_frames.csv", index=False, lineterminator="\n", float_format="%.17g")
    (replay / "initial.state").write_bytes(state.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--initial-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    paths = paths_for(args.db_root.resolve())
    camera = camera_rows(paths)
    markers, nodes = downstream_rows(paths, camera)
    result = export_dataset(args.output, camera, markers, nodes)
    export_replay(args.output, paths["left"], args.initial_state)
    summary = {
        "timezone": "Asia/Shanghai", "window_local": "22:00–次日08:00",
        "main_numeric_precision": "7 decimal places in mm; scale retains 17 significant digits",
        "camera_only_timestamp_ms": INPUT_ONLY, "cross_partition_y0_timestamp_ms": ROLLOVER,
        "partitions": result,
    }
    (args.output / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(camera):,} camera rows, {len(markers):,} marker y0 rows, {len(nodes):,} node y0 rows.")


if __name__ == "__main__":
    main()
