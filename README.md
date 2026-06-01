# AIS Collision Detection

A PySpark pipeline for detecting vessel collision events and near-misses using AIS (Automatic Identification System) data from the Danish Maritime Authority.

## Table of Contents

1. [Detected Event](#detected-event)
2. [Methodology](#methodology)
   - [Data Source](#data-source)
   - [Pipeline Stages](#pipeline-stages)
   - [Performance Optimizations](performance-optimizations)
   - [Collision Criteria](#collision-criteria)
3. [Data Setup](#data-setup)
4. [Usage](#usage)
   - [Docker (Recommended)](#docker-recommended)
   - [Local](#local)
5. [Output](#output)

## Detected Event

![collision](results/collision_trajectory.png)

**Incident Timestamp:** 21 December 2025, 13:00:40 UTC  
**Location:** Baltic Sea (Coordinates: 54.9113°N, 14.8627°E)  

Based on the trajectory data, this is the chronological vessel behavior:

---

**BEFORE THE COLLISION**

**ANRI (MMSI 219012544)**
- Heading: Northwest (COG ~302-309°)
- Speed: Slow (~3 knots)
- Direction of travel: From the southeast toward the northwest

**PROLINER (MMSI 219022341)**
- Heading: Southeast (COG ~137-159°)
- Speed: High (~28-29 knots)
- Direction of travel: From the northwest toward the southeast

They were on a **near head-on collision course** - ANRI going northwest, PROLINER going southeast.

---

**AROUND THE COLLISION (13:00-13:01)**

Both vessels attempted evasive maneuvers:
- PROLINER turned hard to starboard (west, COG ~273°) and decelerated from ~29 knots to nearly stopped
- ANRI turned sharply to port (northeast, COG ~28°) and slowed

---

**AFTER THE COLLISION (13:02 onwards)**

**Both vessels headed northwest at high speed:**
- ANRI: COG ~332-343°, SOG ~19 knots
- PROLINER: COG ~325-338°, SOG ~25 knots

---

**INTERPRETATION**

The most telling indication of collision is that **both vessels proceeded in the same direction after the event** - northwest at high speed. This strongly suggests they coordinated (likely via VHF radio) to proceed together to a nearby harbor or marina to exchange information and report the incident. The fact that PROLINER was traveling *faster* after the collision than ANRI could indicate either that PROLINER's damage was less severe, or that they were both racing to reach port before their vessels took on more water.

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

### Performance Optimizations

Processing a month of AIS data (tens of millions of records) requires careful resource management. Key optimizations include:

- **PySpark over Pandas** — Distributed processing handles datasets larger than memory, with lazy evaluation avoiding unnecessary computation
- **Bounding box pre-filter** — Simple lat/lon range comparison eliminates ~95% of records before the expensive Haversine distance calculation
- **Spatial grid bucketing** — 0.01° grid cells (~1km) constrain the self-join to only compare vessels in the same geographic area, preventing an O(n²) explosion of pairs
- **Temporal aggregation** — 40-second windows reduce ping frequency noise and dramatically shrink the join space
- **Strategic caching** — `.persist(StorageLevel.MEMORY_AND_DISK)` at critical boundaries (after filtering, before the join) breaks the lineage chain and avoids recomputing the entire pipeline on each action
- **Coordinate movement filter** — Simple Euclidean distance between consecutive pings (`sqrt(Δlat² + Δlon²)`) for GPS jump detection, avoiding an additional Haversine computation per record
- **Intermediate column decomposition** — Breaking the Haversine formula into separate `withColumn` steps prevents deeply nested expression trees that exceed Python's recursion limit and complicate Spark's query optimizer

### Collision Criteria

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Collision distance | ≤ 5 meters | Within AIS accuracy range |
| Time tolerance | ≤ 10 seconds | Simultaneous positions |
| Minimum SOG | > 1.0 knot | Both vessels underway |
| Encounter gap | > 5 minutes | Separate close-quarters events |

## Data Setup

The pipeline expects AIS data in CSV format within the `data/` directory. 

To download the December 2025 dataset from the Danish Maritime Authority, use the provided script which fetches all files in parallel:

```bash
chmod +x dl-data.sh
./dl-data.sh
```

Alternatively, you can place your own .csv files directly into the `data/` folder. The schema will be automatically inferred from the files present.

## Usage
### Docker (Recommended)

Pull the image from Docker Hub ([link](https://hub.docker.com/r/tabeh/ais-collision-detector)) and run the pipeline with your local data and results directories mounted

```bash
# Pull the image
docker pull tabeh/ais-collision-detector:latest

# Run the pipeline
docker run -it --rm \
  -v \$(pwd)/data:/app/data \
  -v \$(pwd)/results:/app/results \
  tabeh/ais-collision-detector:latest
```

Note: The `-v` flags mount your local directories into the container. Ensure your AIS CSV files are in the `data/` folder before running. The output visualization and CSVs will be saved to your local `results/` folder.

To build the image locally from the Dockerfile:

```bash
docker build -t ais-collision-detector .
```

and run it with:

```bash
docker run -it --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/results:/app/results \
  ais-collision-detector
```
### Local

If you prefer to run the scripts directly without Docker, ensure you have Python 3.8+, Java, and the required system libraries (GEOS, PROJ) installed.

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the orchestrator
python main.py
```

## Output

Upon completion, the following files will be generated in the `results/` directory:

- `collision_event.csv` — Collision event details
- `collision_trajectory.csv` — 20-minute trajectory data (10 min around the event)
- `collision_trajectory.png` — Visualization with search area overview and trajectory detail
