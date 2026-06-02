#!/usr/bin/python3
"""
AIS Collision Detection Pipeline Orchestrator

Executes the full pipeline:
1. analysis.py - PySpark collision detection
2. visualize.py - Cartopy trajectory visualization
"""

import subprocess
import sys
import time
from pathlib import Path

def run_script(script_name):
    """Run a Python script and report status."""
    print(f"\n{'='*60}")
    print(f"Running {script_name}...")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            capture_output=False,
            text=True
        )
        
        elapsed = time.time() - start_time
        print(f"\n✓ {script_name} completed in {elapsed:.1f}s")
        return True
        
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"\n✗ {script_name} failed after {elapsed:.1f}s")
        print(f"  Exit code: {e.returncode}")
        return False
    
    except FileNotFoundError:
        print(f"\n✗ {script_name} not found")
        return False

def verify_outputs():
    """Verify that expected output files exist."""
    print(f"\n{'='*60}")
    print("Verifying outputs...")
    print(f"{'='*60}\n")
    
    expected_files = [
        "results/collision_event.csv",
        "results/collision_trajectory.csv",
    ]
    
    all_exist = True
    for filepath in expected_files:
        path = Path(filepath)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  ✓ {filepath} ({size_kb:.1f} KB)")
        else:
            print(f"  ✗ {filepath} MISSING")
            all_exist = False
    
    return all_exist

def main():
    print("AIS Collision Detection Pipeline")
    print("=" * 60)
    
    pipeline_start = time.time()
    
    # Step 1: Run analysis
    if not run_script("analysis.py"):
        print("\nPipeline aborted: analysis.py failed")
        sys.exit(1)

    # Step 2: Verify outputs
    if not verify_outputs():
        print("\nPipeline completed with missing outputs")
        sys.exit(1)
    
    # Step 3: Run visualization
    if not run_script("visualize.py"):
        print("\nPipeline aborted: visualize.py failed")
        sys.exit(1)
    
    # Summary
    total_elapsed = time.time() - pipeline_start
    print(f"\n{'='*60}")
    print(f"Pipeline completed successfully in {total_elapsed:.1f}s")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()