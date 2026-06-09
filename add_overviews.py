"""
Add internal overviews to a directory of GeoTIFFs before sharing.

The processing pipeline (merge_daily_masks.py, reproject_to_3413.py) writes single-pass
tiled GeoTIFFs with NO overviews, because nothing downstream reads them and building
them is the dominant write cost. Run this once on the files you're about to distribute
so collaborators get fast zoomed-out viewing. Overviews are built in parallel across
files (the reproject loop is serial and never could).

Usage:
    python add_overviews.py <dir> [levels ...]
    python add_overviews.py ./lake_detection_binary_masks_merged_daily_v2_3413_clipped
    python add_overviews.py ./some_dir 2 4 8 16 32      # custom decimation levels
"""

import glob
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

DEFAULT_LEVELS = ["2", "4", "8", "16", "32", "64"]


def add_overviews(path, levels):
    # Internal overviews, ZSTD-compressed to match the base image. gdaladdo works in
    # blocks (low memory), so several large rasters in parallel is fine.
    subprocess.run(
        ["gdaladdo", "-r", "nearest",
         "--config", "COMPRESS_OVERVIEW", "ZSTD",
         path, *levels],
        check=True,
    )
    return path


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    directory = sys.argv[1]
    levels = sys.argv[2:] or DEFAULT_LEVELS
    files = sorted(glob.glob(os.path.join(directory, "*.tif")))
    if not files:
        sys.exit(f"No .tif files found in {directory}")

    print(f"Adding overviews {levels} to {len(files)} files in {directory}")
    max_workers = min(8, os.cpu_count())
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(add_overviews, f, levels): f for f in files}
        for i, fut in enumerate(as_completed(futs), 1):
            print(f"  [{i}/{len(files)}] {os.path.basename(fut.result())}")

    print("Done")


if __name__ == "__main__":
    main()
