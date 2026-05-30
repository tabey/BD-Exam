# AIS Collision Detection

A PySpark pipeline for detecting vessel collision events and near-misses using AIS (Automatic Identification System) data from the Danish Maritime Authority.

## Table of Contents

1. [Detected Event](#Detected-Event)
2. [Methodology](#Methodology)
   - [Data Source](#Data-Source)
   - [Pipeline Stages](#Pipeline-Stages)
   - [Collision Criteria](#Collision-Criteria)
3. [Usage](#Usage)

## Detected Event

![collision](results/collision_trajectory.png)

On **2025-12-21 at 13:00:40 UTC**, the pipeline identified a close-quarters encounter between two pleasure craft in the Baltic Sea near 54.9113°N, 14.8627°E:

| Vessel | MMSI | Type | Role |
|--------|------|------|------|
| ANRI | 219012544 | Pleasure | Overtaking vessel |
| PROLINER | 219022341 | Pleasure | Vessel being overtaken |

**Minimum distance:** 4.6 meters

**Event classification:** Overtaking near-miss. Both vessels were proceeding south on similar courses when ANRI closed to within AIS accuracy range while overtaking PROLINER. ANRI subsequently altered course approximately 10° to port, consistent with an avoidance maneuver.

## Methodology

### Data Source
- 31 days of AIS data (December 2025) from the Danish Maritime Authority
- Search area: 50 nautical mile radius centered on 55.225°N, 14.245°E

### Pipeline Stages

1. **Spatial Filtering** — Bounding box pre-filter followed by Haversine distance calculation
2. **Data Quality** — Null/invalid coordinate removal, SOG range validation
3. **GPS Jump Detection** — Coordinate movement thresholds to filter AIS noise
4. **Vessel Filtering** — Stationary vessel removal (SOG < 1.0 knot), service vessel exclusion (pilot, tug, SAR, etc.), fishing vessel exclusion
5. **Temporal Aggregation** — 40-second windows to reduce ping frequency noise
6. **Spatiotemporal Join** — Self-join on time bucket and spatial grid (0.01° cells)
7. **Distance Calculation** — Haversine formula between vessel pairs
8. **Deduplication** — Encounter grouping with 5-minute gap threshold, closest-point selection

### Collision Criteria

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Collision distance | ≤ 5 meters | Within AIS accuracy range |
| Time tolerance | ≤ 10 seconds | Simultaneous positions |
| Minimum SOG | > 1.0 knot | Both vessels underway |
| Encounter gap | > 5 minutes | Separate close-quarters events |

## Usage

WIP