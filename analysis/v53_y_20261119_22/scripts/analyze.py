"""Audit the exported Y-axis and y0 observations and write the evidence tables."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
NIGHTS = ("2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22")


@dataclass(frozen=True)
class Event:
    day: int
    line: str
    device: str
    mark: str
    start: int
    stop: int
    extremum: str = "abs"


EVENTS = (
    Event(19,"left","780638310097","ZD1701",435,446),
    Event(19,"left","780638310097","ZD2101",435,446),
    Event(19,"right","780639346578","YD2204",435,446),
    Event(19,"right","780639346578","YD2604",435,446),
    Event(20,"right","780639346578","YD2204",194,201),
    Event(21,"left","780638271319","ZD1403",80,540),
    Event(22,"left","780638271319","ZD1403",80,540),
    Event(21,"right","780639173835","YJ1",225,229,"max"),
    Event(21,"right","780639173835","YJ2",225,229,"max"),
    Event(21,"right","780639173835","YJ1",332,336,"min"),
    Event(21,"right","780639173835","YJ2",332,336,"min"),
    Event(21,"right","780639173835","YJ3",332,336,"min"),
    Event(21,"right","780639173835","YJ4",332,336,"min"),
    Event(22,"right","780639346578","YD2004",80,540),
)


def midnight_offset(night, ts):
    t0 = datetime.fromisoformat(night).replace(hour=22, tzinfo=TZ)
    return (ts - int(t0.timestamp() * 1000)) / 60_000


def interval(data, start, stop):
    return data.offset.ge(start) & data.offset.lt(stop)


def load(root, night, line):
    base = root / night / line
    frames = pd.read_csv(base / "frames.csv")
    frames["offset"] = midnight_offset(night, frames.timestamp_ms)
    frames_with_y0 = set(frames.loc[frames.has_y0.eq(1), "frame_id"])
    assert len(frames_with_y0) == 600

    dims = pd.read_csv(root / "channels.csv", dtype={"device_id": str})
    scales = pd.read_csv(root / "calibration.csv").query("night == @night")
    report = pd.read_csv(base / "camera_y.csv").merge(dims, on="channel_id", validate="many_to_one")
    assert len(report) == len(frames) * (254 if line=="left" else 268) and report.line.eq(line).all()
    assert not report.duplicated(["frame_id", "channel_id"]).any()
    report = report.merge(frames, on="frame_id", validate="many_to_one")
    report = report.merge(scales, on="channel_id", validate="many_to_one")
    report["valid"] = report.roi.eq(1) & np.isfinite(report.y_mm) & np.isfinite(report.cal_y_mm)
    base_y = report[report.valid & interval(report,0,60)].groupby("channel_id").y_mm.agg(["mean","size"])
    assert base_y["size"].ge(10).all()
    report = report.join(base_y["mean"].rename("base_y"), on="channel_id")
    report["raw_px"] = ((report.y_mm - report.base_y) * report.scale_px_per_mm).where(report.valid)
    report["cal_px"] = ((report.cal_y_mm - report.base_y) * report.scale_px_per_mm).where(report.valid)
    report["deduct_px"] = report.raw_px - report.cal_px
    assert report.loc[report.valid,"cal_px"].notna().all()

    def output(file, lookup, key, count):
        raw = pd.read_csv(base / file)
        assert set(raw.frame_id) == frames_with_y0
        assert not raw.duplicated(["frame_id",key]).any()
        assert raw.groupby("frame_id").size().eq(count).all()
        values = raw.merge(lookup, on=key, validate="many_to_one").merge(
            frames[["frame_id","timestamp_ms","local_time","offset"]], on="frame_id", validate="many_to_one")
        assert values.line.eq(line).all() and np.isfinite(values.y0_mm).all()
        return values
    marks = output("marker_y0.csv",pd.read_csv(root/"markers.csv"),"point_id",191 if line=="left" else 200)
    nodes = output("node_y0.csv",pd.read_csv(root/"devices.csv",dtype={"device_id":str}),"node_id",6)
    return report,marks,nodes


def selected_event(event, tables):
    camera, marks, _ = tables
    owned = camera[camera.device_id.eq(event.device) & camera.marker_name.eq(event.mark)]
    w = owned.loc[owned.valid & interval(owned,event.start,event.stop)]
    if event.extremum == "min":
        pos = w.cal_px.idxmin()
    elif event.extremum == "max":
        pos = w.cal_px.idxmax()
    else:
        pos = w.cal_px.abs().idxmax()
    sample = w.loc[pos]
    peers = camera[camera.timestamp_ms.eq(sample.timestamp_ms) & camera.device_id.eq(event.device)
                   & camera.valid & camera.marker_name.ne(event.mark)]
    others = camera[camera.device_id.ne(event.device) & camera.marker_name.eq(event.mark)
                    & interval(camera,event.start,event.stop) & camera.valid]
    backups = others.loc[others.timestamp_ms.eq(sample.timestamp_ms)].set_index("device_id").cal_px.to_dict()
    backup_window = others.groupby("device_id").cal_px.agg(lambda a:a.abs().max()).to_dict()
    mark_y0 = marks.loc[marks.timestamp_ms.eq(sample.timestamp_ms) & marks.marker_name.eq(event.mark),"y0_mm"]
    whole = owned[interval(owned,80,540)]
    return {
        "night": f"2026-11-{event.day}", "line":event.line, "device_id":event.device, "marker_name":event.mark,
        "peak_local_time":sample.local_time, "raw_px":sample.raw_px, "cal_px":sample.cal_px,
        "deduct_px":sample.deduct_px, "peer_median_cal_px":peers.cal_px.median(),
        "peer_count":len(peers), "peer_abs_gt_2px":int(peers.cal_px.abs().gt(2).sum()),
        "alternate_cal_px_same_frame":";".join(f"{dev}={value:.6f}" for dev,value in backups.items()),
        "alternate_max_abs_px_in_window":";".join(f"{dev}={value:.6f}" for dev,value in backup_window.items()),
        "y0_same_frame_mm":mark_y0.iloc[0] if len(mark_y0) else np.nan,
        "valid_frames_in_core":int(whole.valid.sum()), "total_frames_in_core":len(whole),
        "frames_corrected_in_core":int(whole.deduct_px.abs().gt(1e-7).sum()),
    }


def variance_span(x):
    return x.quantile(.95) - x.quantile(.05)


def nightly(night, line, tables):
    camera, points, _ = tables
    q = camera.loc[camera.valid & interval(camera,80,540)].copy()
    peak = q.loc[q.cal_px.abs().idxmax()]
    solved = points[interval(points,80,540)].groupby("marker_name").y0_mm.agg(["min","max",variance_span])
    varied = solved[solved["min"].ne(solved["max"])]
    return {
        "night":night, "line":line, "camera_rows":len(camera),
        "valid_camera_rows":int(camera.valid.sum()), "valid_in_core":len(q),
        "abs_le_1px":int(q.cal_px.abs().le(1).sum()),
        "abs_gt_2px":int(q.cal_px.abs().gt(2).sum()),
        "abs_gt_3px":int(q.cal_px.abs().gt(3).sum()),
        "peak_cal_px":peak.cal_px, "peak_marker":peak.marker_name,
        "peak_device":peak.device_id, "peak_local_time":peak.local_time,
        "y0_points_with_variation":len(varied),
        "y0_median_point_p95_minus_p5_mm":varied.variance_span.median(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data",type=Path,default=ROOT/"data")
    ap.add_argument("--output",type=Path,default=ROOT/"evidence")
    args = ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    summaries, event_rows = [], []
    for night in NIGHTS:
        for line in ("left","right"):
            tables = load(args.data,night,line)
            summaries.append(nightly(night,line,tables))
            for event in EVENTS:
                if f"2026-11-{event.day}" == night and event.line == line:
                    event_rows.append(selected_event(event,tables))
            if (night,line) == ("2026-11-21","right"):
                _,points,nodes = tables
                anchors = points[points.marker_name.isin(["YJ1","YJ2","YJ3","YJ4"])]
                assert anchors.y0_mm.eq(0).all()
                relevant = nodes[interval(nodes,330,338) & nodes.device_id.isin(
                    ["780639346578","780639376393","780639414923"])]
                relevant[["local_time","device_id","y0_mm"]].to_csv(
                    args.output/"1121_right_node_event.csv",index=False,lineterminator="\n",float_format="%.7f")

    summary = pd.DataFrame(summaries)
    assert summary.camera_rows.sum() == 1_253_054
    assert summary.valid_camera_rows.sum() == 1_243_327
    assert summary.valid_in_core.sum() == 953_497 and summary.abs_le_1px.sum() == 952_389
    assert summary.abs_gt_3px.sum() == 50
    event = pd.DataFrame(event_rows)
    assert len(event) == len(EVENTS)
    zd = event[event.marker_name.eq("ZD1403")]
    assert zd.frames_corrected_in_core.eq(0).all() and list(zd.valid_frames_in_core) == [180,432]
    summary.to_csv(args.output/"nightly_summary.csv",index=False,lineterminator="\n",float_format="%.7f")
    event.to_csv(args.output/"point_events.csv",index=False,lineterminator="\n",float_format="%.7f")
    print(summary[["night","line","valid_in_core","abs_le_1px","peak_cal_px","peak_marker"]].to_string(index=False))
    print(f"Core |calY relative to baseline| <= 1 px: {summary.abs_le_1px.sum()/summary.valid_in_core.sum():.4%}")


if __name__ == "__main__":
    main()
