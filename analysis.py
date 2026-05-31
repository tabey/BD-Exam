#!/usr/bin/python3
import sys
sys.setrecursionlimit(10000)

from pyspark.sql import SparkSession
from pyspark.sql.types import *
from pyspark.sql.functions import (
    col, radians, sin, cos, sqrt, atan2, lit, degrees,
    when, lag, unix_timestamp,
    min as spark_min, max as spark_max, sum as spark_sum,
    floor, abs as spark_abs, first, row_number,
    pow as spark_pow, last, expr
)
from pyspark.sql.window import Window
from pyspark.storagelevel import StorageLevel

import math
import os
from datetime import timedelta

def run_analysis():
    spark = SparkSession.builder \
        .appName("AIS-Collision-Detection") \
        .master("local[*]") \
        .config("spark.sql.session.timeZone", "UTC") \
        .config("spark.driver.memory", "8g") \
        .config("spark.driver.maxResultSize", "2g") \
        .config("spark.memory.fraction", "0.8") \
        .config("spark.memory.storageFraction", "0.3") \
        .getOrCreate()
    
    # Infer from one file
    df_sample = spark.read.csv(
        'data/aisdk-2025-12-31.csv',
        header=True,
        inferSchema=True,
        timestampFormat="dd/MM/yyyy HH:mm:ss",
    )
    
    inferred_schema = df_sample.schema
    
    # Read all files with the correct schema
    df = spark.read.csv(
        'data/',
        header=True,
        schema=inferred_schema,
        timestampFormat="dd/MM/yyyy HH:mm:ss",
        locale="da_DK",
    )

    # Center point
    center_lat = 55.225
    center_lon = 14.245
    
    # Radius in nautical miles
    radius_nm = 50
    
    lat_offset = radius_nm / 60.0
    lon_offset = radius_nm / (60.0 * math.cos(math.radians(center_lat)))
    
    # Pre-filter with bounding box
    df_filtered = df.filter(
        (col("Latitude").between(center_lat - lat_offset, center_lat + lat_offset)) &
        (col("Longitude").between(center_lon - lon_offset, center_lon + lon_offset))
    )
    
    # Haversine distance from center point (broken into intermediate columns)
    R_nm = 3440.065
    
    df_filtered = df_filtered \
        .withColumn("lat1", lit(math.radians(center_lat))) \
        .withColumn("lon1", lit(math.radians(center_lon))) \
        .withColumn("lat2", radians(col("Latitude"))) \
        .withColumn("lon2", radians(col("Longitude"))) \
        .withColumn("dlat", col("lat2") - col("lat1")) \
        .withColumn("dlon", col("lon2") - col("lon1")) \
        .withColumn("sin_dlat", sin(col("dlat") / 2)) \
        .withColumn("sin_dlon", sin(col("dlon") / 2)) \
        .withColumn("a", col("sin_dlat") ** 2 + cos(col("lat1")) * cos(col("lat2")) * col("sin_dlon") ** 2) \
        .withColumn("c", 2 * atan2(sqrt(col("a")), sqrt(1 - col("a")))) \
        .withColumn("distance_nm", lit(R_nm) * col("c"))
    
    # Filter within radius
    df_radius = df_filtered.filter(col("distance_nm") <= radius_nm) \
        .drop("lat1", "lon1", "lat2", "lon2", "dlat", "dlon", "sin_dlat", "sin_dlon", "a", "c", "distance_nm")
    
    # Basic data quality filtering
    df_clean = df_radius.filter(
        (col("Latitude").isNotNull()) &
        (col("Longitude").isNotNull()) &
        (col("MMSI").isNotNull()) &
        (col("Latitude").between(-90, 90)) &
        (col("Longitude").between(-180, 180)) &
        ~((col("Latitude") == 0) & (col("Longitude") == 0)) &
        (col("SOG").isNull() | (col("SOG") <= 50))
    )
    
    # GPS jump detection using coordinate movement (simpler and more reliable)
    vessel_window = Window.partitionBy("MMSI").orderBy("# Timestamp")
    
    df_with_prev = df_clean \
        .withColumn("prev_lat", lag("Latitude").over(vessel_window)) \
        .withColumn("prev_lon", lag("Longitude").over(vessel_window)) \
        .withColumn("prev_timestamp", lag("# Timestamp").over(vessel_window))
    
    # Simple coordinate movement
    df_with_prev = df_with_prev.withColumn(
        "movement",
        sqrt(
            spark_pow(col("Latitude") - col("prev_lat"), 2) +
            spark_pow(col("Longitude") - col("prev_lon"), 2)
        )
    )
    
    # Filter out stationary vessels and GPS jumps
    df_no_jumps = df_with_prev.filter(
        col("movement").isNotNull() &
        (col("movement") > 0.00005) &  # Minimum movement threshold
        (col("movement") < 0.02)       # Maximum movement (GPS anomalies)
    ).drop("prev_lat", "prev_lon", "prev_timestamp", "movement")
    
    # Filter for moving vessels
    MIN_SPEED = 1.0
    
    df_moving = df_no_jumps.filter(
        col("SOG") > MIN_SPEED
    )

    # Filter out service vessels and fishing vessels
    service_types = [
        "Pilot",
        "Tug",
        "Port tender",
        "SAR",
        "Law enforcement",
        "Towing",
        "Towing long/wide",
        "Dredging",
        "Fishing",  # Fishing vessels cluster by nature
    ]

    df_moving = df_moving.filter(
        ~col("Ship type").isin(service_types) | col("Ship type").isNull()
    )

    # Filter out rescue vessels by name pattern
    df_moving = df_moving.filter(
        ~col("Name").rlike("(?i)(RESCUE|KBV)")
    )

    df_moving.persist(StorageLevel.MEMORY_AND_DISK)
    
    # Collision detection
    COLLISION_DISTANCE_M = 5  # Back to 5m
    TIME_TOLERANCE_SECONDS = 10

    from pyspark.sql.functions import floor as spark_floor
    GRID_SIZE = 0.01
    
    df_bucketed = df_moving \
        .withColumn(
            "time_bucket",
            (floor(unix_timestamp("# Timestamp") / 40) * 40).cast("timestamp")  # 40-sec windows
        ) \
        .withColumn("grid_lat", spark_floor(col("Latitude") / GRID_SIZE) * GRID_SIZE) \
        .withColumn("grid_lon", spark_floor(col("Longitude") / GRID_SIZE) * GRID_SIZE)

    # Aggregate to one position per vessel per time window
    df_aggregated = df_bucketed.groupBy(
        "MMSI",
        "time_bucket",
        "grid_lat",
        "grid_lon"
    ).agg(
        last("Latitude").alias("Latitude"),
        last("Longitude").alias("Longitude"),
        last("SOG").alias("SOG"),
        last("COG").alias("COG"),
        first("Name").alias("Name"),
        first("Ship type").alias("Ship type")
    )

    df_join_ready = df_aggregated.select(
        col("MMSI"),
        col("time_bucket"),
        col("Latitude"),
        col("Longitude"),
        col("SOG"),
        col("COG"),
        col("Name"),
        col("grid_lat"),
        col("grid_lon")
    )

    df_join_ready.persist(StorageLevel.MEMORY_AND_DISK)
    
    # Self-join: find vessel pairs in the same time bucket
    df_pairs = df_join_ready.alias("v1").join(
        df_join_ready.alias("v2"),
        (col("v1.time_bucket") == col("v2.time_bucket")) &
        (col("v1.grid_lat") == col("v2.grid_lat")) &
        (col("v1.grid_lon") == col("v2.grid_lon")) &
        (col("v1.MMSI") < col("v2.MMSI"))
    )

    # REMOVED: Convergence check - too strict for crossing courses
    
    # Both vessels must be moving
    df_pairs = df_pairs.filter(
        (col("v1.SOG") > MIN_SPEED) & (col("v2.SOG") > MIN_SPEED)
    )
    
    # Haversine between vessel pairs (broken into intermediate columns)
    R_m = 6371000
    
    df_pairs = df_pairs \
        .withColumn("lat1", radians(col("v1.Latitude"))) \
        .withColumn("lon1", radians(col("v1.Longitude"))) \
        .withColumn("lat2", radians(col("v2.Latitude"))) \
        .withColumn("lon2", radians(col("v2.Longitude"))) \
        .withColumn("dlat", col("lat2") - col("lat1")) \
        .withColumn("dlon", col("lon2") - col("lon1")) \
        .withColumn("sin_dlat", sin(col("dlat") / 2)) \
        .withColumn("sin_dlon", sin(col("dlon") / 2)) \
        .withColumn("a", col("sin_dlat") ** 2 + cos(col("lat1")) * cos(col("lat2")) * col("sin_dlon") ** 2) \
        .withColumn("c", 2 * atan2(sqrt(col("a")), sqrt(1 - col("a")))) \
        .withColumn("distance_m", lit(R_m) * col("c"))
    
    df_collisions = df_pairs.filter(col("distance_m") <= COLLISION_DISTANCE_M)
    
    # Select relevant columns
    df_collisions = df_collisions.select(
        col("v1.MMSI").alias("mmsi_1"),
        col("v2.MMSI").alias("mmsi_2"),
        col("v1.Name").alias("name_1"),
        col("v2.Name").alias("name_2"),
        col("v1.time_bucket").alias("timestamp_1"),  # Changed from timestamp
        col("v2.time_bucket").alias("timestamp_2"),  # Changed from timestamp
        col("v1.Latitude").alias("lat_1"),
        col("v1.Longitude").alias("lon_1"),
        col("v2.Latitude").alias("lat_2"),
        col("v2.Longitude").alias("lon_2"),
        col("distance_m")
    )

    # Deduplicate collision events
    encounter_window = Window.partitionBy("mmsi_1", "mmsi_2").orderBy("timestamp_1")

    df_collisions = df_collisions.withColumn(
        "prev_t1", lag("timestamp_1").over(encounter_window)
    ).withColumn(
        "new_encounter",
        when(
            (unix_timestamp("timestamp_1") - unix_timestamp("prev_t1")) > 300,
            1
        ).otherwise(0)
    )

    df_collisions = df_collisions.withColumn(
        "encounter_id",
        spark_sum("new_encounter").over(
            Window.partitionBy("mmsi_1", "mmsi_2").orderBy("timestamp_1")
        )
    )

    window_closest = Window.partitionBy("mmsi_1", "mmsi_2", "encounter_id") \
        .orderBy("distance_m")

    df_collisions = df_collisions.withColumn(
        "rank", row_number().over(window_closest)
    )

    df_unique_collisions = df_collisions.filter(col("rank") == 1) \
        .drop("prev_t1", "new_encounter", "encounter_id", "rank")


    print(f"Unique collision events: {df_unique_collisions.count()}")
    df_unique_collisions.orderBy("distance_m").show(20, truncate=False)

    # Extract trajectory for the first collision event
    if df_unique_collisions.count() > 0:
        # Get the collision details
        collision_row = df_unique_collisions.first()
        mmsi_1 = collision_row["mmsi_1"]
        mmsi_2 = collision_row["mmsi_2"]
        collision_time = collision_row["timestamp_1"]

        # Calculate time window
        start_time = collision_time - timedelta(minutes=10)
        end_time = collision_time + timedelta(minutes=10)

        # Use df_clean instead of df_moving to get the full trajectory
        df_trajectory = df_clean.filter(
            ((col("MMSI") == mmsi_1) | (col("MMSI") == mmsi_2)) &
            (col("# Timestamp") >= lit(start_time)) &
            (col("# Timestamp") <= lit(end_time))
        ).select(
            col("MMSI"),
            col("# Timestamp").alias("timestamp"),
            col("Latitude"),
            col("Longitude"),
            col("SOG"),
            col("COG"),
            col("Ship type")
        ).orderBy("MMSI", "timestamp")

        # Check if we got any data
        trajectory_count = df_trajectory.count()
        print(f"Trajectory points found: {trajectory_count}")

        if trajectory_count > 0:
            df_trajectory.show(50, truncate=False)
            
            # Save trajectory data for visualize.py
            pd_trajectory = df_trajectory.toPandas()
            pd_trajectory.to_csv('results/collision_trajectory.csv', index=False)

        # Save collision event details
        pd_collisions = df_unique_collisions.toPandas()
        pd_collisions.to_csv('results/collision_event.csv', index=False)

        # Get vessel details
        vessel_info = df_moving.filter(
            (col("MMSI") == mmsi_1) | (col("MMSI") == mmsi_2)
        ).select(
            "MMSI", "Name", "Ship type", "Length", "Width", "Destination"
        ).distinct()

        vessel_info.show(truncate=False)
    
    spark.stop()

if __name__ == '__main__':
    run_analysis()
