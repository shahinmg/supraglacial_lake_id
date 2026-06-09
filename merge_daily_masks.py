"""
Merge outputs from lake_detect_parallel.py
method="max" is logical OR for binary mask merging
"""
import gc
import os
import glob
from collections import defaultdict
from multiprocessing import Pool, cpu_count

import rasterio
from rasterio.merge import merge


MASK_DIR = "./lake_detection_binary_masks_parallel_v2"
OUT_DIR = "./lake_detection_binary_masks_merged_daily_v2"

# Set to "YYYYMMDD" strings to restrict processing, or None to process all dates
DATE_START = "20180501"
DATE_END = "20190930"


def merge_date(args):
    date, files = args
    out_path = os.path.join(OUT_DIR, f"{date}_merged_lake_pixels.tif")

    if os.path.exists(out_path):
        print(f"Skipping {date} (already exists)")
        return

    print(f"Merging {len(files)} file(s) for {date}")
    datasets = [rasterio.open(f) for f in files]
    try:
        # method="max" is logical OR for binary [0, 1] masks
        mosaic, transform = merge(datasets, method="max")
        meta = datasets[0].meta.copy()
        meta.update({
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": transform,
        })
    finally:
        for ds in datasets:
            ds.close()

    item_ids = [os.path.basename(f).replace("_lake_pixels.tif", "") for f in files]
    # Single-pass tiled write, no overviews (nothing downstream reads them).
    meta.update(driver="GTiff", count=1, tiled=True, blockxsize=512, blockysize=512,
                compress="zstd", zstd_level=6)
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(mosaic[0], 1)
        dst.update_tags(source_items=",".join(item_ids))
    del mosaic
    gc.collect()

# TO READ: rasterio.open(path).tags()["source_items"].split(",") 
def group_files_by_date(mask_dir):
    by_date = defaultdict(list)
    for f in glob.glob(os.path.join(mask_dir, "**", "*.tif"), recursive=True):
        # filename: S2A_T22WEA_20200511T151914_L2A_lake_pixels.tif
        date = os.path.basename(f).split("_")[2][:8]
        by_date[date].append(f)
    return dict(by_date)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    by_date = group_files_by_date(MASK_DIR)
    if DATE_START:
        by_date = {d: f for d, f in by_date.items() if d >= DATE_START}
    if DATE_END:
        by_date = {d: f for d, f in by_date.items() if d <= DATE_END}
    print(f"Found {len(by_date)} dates with multiple files to merge")

    with Pool(processes=min(6, cpu_count())) as pool:
        pool.map(merge_date, list(by_date.items()))

    print("Done")
