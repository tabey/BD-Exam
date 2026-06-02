#!/usr/bin/python3
import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.geodesic import Geodesic
import shapely.geometry as sgeom
import math
import os

# Search parameters from analysis.py
CENTER_LAT = 55.225
CENTER_LON = 14.245
RADIUS_NM = 50

def plot_single_collision(event_id, collision_row, df_traj):
    """Generate and save a visualization for a single collision event."""
    
    # Get collision details
    mmsi_1 = collision_row['mmsi_1']
    mmsi_2 = collision_row['mmsi_2']
    collision_time = pd.to_datetime(collision_row['timestamp_1'])
    collision_lat = collision_row['lat_1']
    collision_lon = collision_row['lon_1']
    distance_m = collision_row['distance_m']
    
    # Get vessel names
    name_1 = collision_row.get('name_1', str(mmsi_1))
    name_2 = collision_row.get('name_2', str(mmsi_2))
    if pd.isna(name_1): name_1 = str(mmsi_1)
    if pd.isna(name_2): name_2 = str(mmsi_2)
    
    # Filter trajectory for this specific event
    event_traj = df_traj[df_traj['event_id'] == event_id].copy()
    event_traj['timestamp'] = pd.to_datetime(event_traj['timestamp'])
    
    # Separate vessels
    vessel_1 = event_traj[event_traj['MMSI'] == mmsi_1].sort_values('timestamp')
    vessel_2 = event_traj[event_traj['MMSI'] == mmsi_2].sort_values('timestamp')
    
    # Calculate map extent for collision detail
    all_lats = event_traj['Latitude'].values
    all_lons = event_traj['Longitude'].values
    
    lat_center = collision_lat
    lon_center = collision_lon
    
    lat_range = max(all_lats) - min(all_lats)
    lon_range = max(all_lons) - min(all_lons)
    
    lat_margin = max(lat_range * 0.6, 0.005)
    lon_margin = max(lon_range * 0.6, 0.005)
    
    detail_extent = [
        lon_center - lon_margin,
        lon_center + lon_margin,
        lat_center - lat_margin,
        lat_center + lat_margin
    ]
    
    # Full search radius extent
    radius_deg_lat = RADIUS_NM / 60.0
    radius_deg_lon = RADIUS_NM / (60.0 * math.cos(math.radians(CENTER_LAT)))
    
    search_extent = [
        CENTER_LON - radius_deg_lon,
        CENTER_LON + radius_deg_lon,
        CENTER_LAT - radius_deg_lat,
        CENTER_LAT + radius_deg_lat
    ]
    
    # Create the search radius circle
    radius_m = RADIUS_NM * 1852
    circle_points = Geodesic().circle(
        lon=CENTER_LON,
        lat=CENTER_LAT,
        radius=radius_m,
        n_samples=100
    )
    search_circle = sgeom.Polygon(circle_points)
    
    # Create figure with two subplots
    fig = plt.figure(figsize=(20, 10))
    
    # ============================================
    # LEFT: Full search area with collision marker
    # ============================================
    ax1 = fig.add_subplot(1, 2, 1, projection=ccrs.Mercator())
    ax1.set_extent(search_extent, crs=ccrs.PlateCarree())
    
    ax1.add_feature(cfeature.LAND, facecolor='#f0f0f0', edgecolor='black', linewidth=0.5)
    ax1.add_feature(cfeature.OCEAN, facecolor='#e6f2ff')
    ax1.add_feature(cfeature.COASTLINE, linewidth=1.0)
    
    ax1.add_geometries(
        [search_circle],
        crs=ccrs.PlateCarree(),
        facecolor='green',
        alpha=0.1,
        edgecolor='green',
        linewidth=2,
        linestyle='--',
        label=f'Search Radius ({RADIUS_NM} nm)'
    )
    
    ax1.plot(
        CENTER_LON, CENTER_LAT,
        marker='+', markersize=12, color='green',
        markeredgewidth=2, transform=ccrs.PlateCarree(),
        zorder=8, label='Search Center'
    )
    
    ax1.plot(
        collision_lon, collision_lat,
        marker='X', markersize=12, color='red',
        markeredgecolor='black', markeredgewidth=1.5,
        transform=ccrs.PlateCarree(), zorder=10, label='Collision'
    )
    
    gl1 = ax1.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5, linestyle='--')
    gl1.top_labels = False
    gl1.right_labels = False
    
    ax1.set_title(
        f'Search Area Overview\n{RADIUS_NM} nm Radius from {CENTER_LAT}°N, {CENTER_LON}°E',
        fontsize=12, fontweight='bold'
    )
    ax1.legend(loc='lower left', fontsize=8, framealpha=0.9)
    
    # ============================================
    # RIGHT: Collision detail with trajectories
    # ============================================
    ax2 = fig.add_subplot(1, 2, 2, projection=ccrs.Mercator())
    ax2.set_extent(detail_extent, crs=ccrs.PlateCarree())
    
    ax2.add_feature(cfeature.LAND, facecolor='#f0f0f0', edgecolor='black', linewidth=0.5)
    ax2.add_feature(cfeature.OCEAN, facecolor='#e6f2ff')
    ax2.add_feature(cfeature.COASTLINE, linewidth=1.0)
    ax2.add_feature(cfeature.LAKES, facecolor='#e6f2ff', edgecolor='black', linewidth=0.3)
    
    gl2 = ax2.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5, linestyle='--')
    gl2.top_labels = False
    gl2.right_labels = False
    
    # Plot vessel 1
    if len(vessel_1) > 1:
        ax2.plot(
            vessel_1['Longitude'].values, vessel_1['Latitude'].values,
            color='red', linewidth=2, marker='o', markersize=4,
            markerfacecolor='red', markeredgecolor='darkred', markeredgewidth=0.5,
            label=f'{name_1} (MMSI: {mmsi_1})', transform=ccrs.PlateCarree(), zorder=5
        )
        ax2.plot(
            vessel_1['Longitude'].iloc[0], vessel_1['Latitude'].iloc[0],
            marker='^', markersize=10, color='red', markeredgecolor='darkred',
            transform=ccrs.PlateCarree(), zorder=6
        )
    
    # Plot vessel 2
    if len(vessel_2) > 1:
        ax2.plot(
            vessel_2['Longitude'].values, vessel_2['Latitude'].values,
            color='blue', linewidth=2, marker='o', markersize=4,
            markerfacecolor='blue', markeredgecolor='darkblue', markeredgewidth=0.5,
            label=f'{name_2} (MMSI: {mmsi_2})', transform=ccrs.PlateCarree(), zorder=5
        )
        ax2.plot(
            vessel_2['Longitude'].iloc[0], vessel_2['Latitude'].iloc[0],
            marker='^', markersize=10, color='blue', markeredgecolor='darkblue',
            transform=ccrs.PlateCarree(), zorder=6
        )
    
    # Mark collision point
    ax2.plot(
        collision_lon, collision_lat,
        marker='X', markersize=15, color='yellow',
        markeredgecolor='black', markeredgewidth=2,
        transform=ccrs.PlateCarree(), zorder=10, label='Collision Point'
    )
    
    # Info text box
    info_text = (
        f"Collision Event #{event_id}\n"
        f"Date: {collision_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Distance: {distance_m:.1f} m\n"
        f"Position: {collision_lat:.4f}°N, {collision_lon:.4f}°E"
    )
    
    ax2.text(
        0.02, 0.98, info_text,
        transform=ax2.transAxes, fontsize=10, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8), zorder=15
    )
    
    ax2.legend(loc='lower right', fontsize=9, framealpha=0.9, edgecolor='black')
    
    ax2.set_title(
        f'Collision Detail - {collision_time.strftime("%Y-%m-%d")}\n'
        f'20-Minute Trajectory Window (±10 min)',
        fontsize=12, fontweight='bold'
    )
    
    # Save and close
    plt.tight_layout()
    output_path = f'results/collision_event_{event_id}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"  ✓ Saved visualization: {output_path}")

def plot_all_collisions():
    # Read the data
    df_traj = pd.read_csv('results/collision_trajectory.csv')
    df_event = pd.read_csv('results/collision_event.csv')
    
    total_events = len(df_event)
    print(f"Found {total_events} collision events to visualize...")
    
    # Ensure results directory exists
    os.makedirs('results', exist_ok=True)
    
    # Loop through all events
    for idx, row in df_event.iterrows():
        event_id = row['event_id']
        print(f"\nProcessing event {event_id}...")
        plot_single_collision(event_id, row, df_traj)
    
    print(f"\nAll {total_events} visualizations complete.")

if __name__ == '__main__':
    plot_all_collisions()