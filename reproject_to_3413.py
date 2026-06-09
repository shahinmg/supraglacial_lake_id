"""
Reproject COGs from EPSG:32622 to EPSG:3413 and clip to the NSIDC-0793 (Greene 2024)
"""

import gc
import os
import glob
from datetime import datetime

import numpy as np
import xarray as xr
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, reproject as warp_reproject


IN_DIR  = "./lake_detection_binary_masks_merged_daily_v2"
OUT_DIR = "./lake_detection_binary_masks_merged_daily_v2_3413_clipped"
NC_PATH = "./NSIDC-0793_19720915-20220215_V01.0.nc"

DST_CRS       = CRS.from_epsg(3413)
DST_RES       = 10.0
DST_WIDTH     = 26088
DST_HEIGHT    = 52904
DST_TRANSFORM = from_origin(-257670.0, -1943680.0, DST_RES, DST_RES)



def load_ice_masks(nc_path):
    """Return the xarray dataset, times array, and source transform for the NC."""
    ds = xr.open_dataset(nc_path)
    times = ds.time.values
    nc_res = 120.0
    nc_transform = from_origin(
        float(ds.x[0]) - nc_res / 2,
        float(ds.y[0]) + nc_res / 2,
        nc_res, nc_res,
    )
    return ds, times, nc_transform


def get_warped_mask(ds, times, nc_transform, date_str, cache):
    """Return a warped ice mask for the closest date, using a cache."""
    cog_dt = np.datetime64(datetime.strptime(date_str, "%Y%m%d"))
    tidx   = int(np.abs(times - cog_dt).argmin())

    if tidx not in cache:
        print(f"  warping ice mask for time slice {tidx} ({times[tidx]})")
        nc_slice = ds["ice_mask"].isel(time=tidx).values

        warped = np.zeros((DST_HEIGHT, DST_WIDTH), dtype=np.int8)
        warp_reproject(
            source=nc_slice,
            destination=warped,
            src_transform=nc_transform,
            src_crs=DST_CRS,
            dst_transform=DST_TRANSFORM,
            dst_crs=DST_CRS,
            resampling=Resampling.nearest,
        )
        cache[tidx] = warped

    return cache[tidx]


def process(src_path, ds, times, nc_transform, mask_cache):
    fname    = os.path.basename(src_path)
    dst_path = os.path.join(OUT_DIR, fname)

    if os.path.exists(dst_path):
        print(f"  skip (exists): {fname}")
        return

    print(f"  processing: {fname}")
    ice_mask = get_warped_mask(ds, times, nc_transform, fname[:8], mask_cache)

    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(
            crs=DST_CRS,
            transform=DST_TRANSFORM,
            width=DST_WIDTH,
            height=DST_HEIGHT,
        )
        data = np.zeros((DST_HEIGHT, DST_WIDTH), dtype=profile["dtype"])
        reproject(
            source=rasterio.band(src, 1),
            destination=data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=DST_TRANSFORM,
            dst_crs=DST_CRS,
            resampling=Resampling.nearest,
            num_threads=os.cpu_count(),
        )
        tags = src.tags()

    data[ice_mask == 0] = 0
    # Single-pass tiled write, no overviews. These are the shared deliverables, so add
    # overviews before distributing with: python add_overviews.py <OUT_DIR>
    # num_threads multithreads zstd compression; safe since reproject runs one process.
    profile.update(driver="GTiff", count=1, tiled=True, blockxsize=512, blockysize=512,
                   compress="zstd", zstd_level=9, num_threads="ALL_CPUS")
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(**tags)

    gc.collect()
    print(f"  done: {fname}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    ds, times, nc_transform = load_ice_masks(NC_PATH)
    mask_cache = {}

    files = sorted(glob.glob(os.path.join(IN_DIR, "*.tif")))
    print(f"Found {len(files)} files")

    # Sequential to keep mask cache efficient across dates. ALL_CPUS multithreads
    # zstd decompression on read and compression on the COG write; safe to max out
    # since there's only one process.
    with rasterio.Env(GDAL_NUM_THREADS="ALL_CPUS"):
        for f in files:
            process(f, ds, times, nc_transform, mask_cache)

    ds.close()
    print("Done")
