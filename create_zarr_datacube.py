#!/usr/bin/env python3
"""
Build a Zarr datacube from all clipped COGs.
Variables: ndwi_mask, source_items (STAC IDs)
Coords: x, y, time

Writes incrementally — one file at a time — to avoid OOM.
"""

import glob
import os
from datetime import datetime

import numpy as np
import xarray as xr
import rioxarray  # noqa: F401  registers .rio accessor
import zarr
from zarr.codecs import ZstdCodec

COG_DIR    = "./lake_detection_binary_masks_merged_daily_v2_cog_3413_clipped"
OUT_ZARR   = "./lake_detection_binary_masks_2019.zarr"
START_DATE = "20190501"  # inclusive, YYYYMMDD
END_DATE   = "20190930"  # inclusive, YYYYMMDD

start_dt = datetime.strptime(START_DATE, "%Y%m%d")
end_dt   = datetime.strptime(END_DATE,   "%Y%m%d")

all_files = sorted(glob.glob(os.path.join(COG_DIR, "*.tif")))
files = [
    f for f in all_files
    if start_dt <= datetime.strptime(os.path.basename(f)[:8], "%Y%m%d") <= end_dt
]
print(f"Found {len(all_files)} total files, {len(files)} within {START_DATE}–{END_DATE}")

encoding = {"ndwi_mask": {"compressors": ZstdCodec(level=9)}}

stac_ids = []

for i, f in enumerate(files):
    date_str = os.path.basename(f)[:8]
    dt       = datetime.strptime(date_str, "%Y%m%d")

    da      = rioxarray.open_rasterio(f, lock=False, chunks={"x": 512, "y": 512}).squeeze("band", drop=True)
    stac_id = da.attrs.get("source_items", "")
    stac_ids.append(stac_id)

    da      = da.expand_dims(time=[np.datetime64(dt)])
    da.name = "ndwi_mask"
    ds_i    = da.to_dataset()

    if i == 0:
        ds_i.attrs = {
            "crs": "EPSG:3413",
            "description": "~Daily NDWI masks clipped to Greenland ice sheet extent",
            "resolution_m": 10,
            "cloud_percentage filter": "10%",
            "ice_sheet_masks": "https://www.doi.org/10.5067/579TO87M7IZB",
            "ice_sheet_masks_citation": "Greene, C.A., Gardner, A.S., Wood, M. et al. Ubiquitous acceleration in Greenland Ice Sheet calving from 1985 to 2022. Nature.",
        }
        ds_i["ndwi_mask"].attrs = {
            "long_name": "NDWI-derived water mask",
            "flag_values": [0, 1],
            "flag_meanings": "no_lake, lake",
            "NDWI_threshold": ">0.3",
        }
        ds_i.chunk({"time": 1, "y": 512, "x": 512}).to_zarr(
            OUT_ZARR, mode="w", encoding=encoding, consolidated=False
        )
    else:
        ds_i.chunk({"time": 1, "y": 512, "x": 512}).to_zarr(
            OUT_ZARR, append_dim="time", consolidated=False
        )

    print(f"  wrote {i+1}/{len(files)}: {os.path.basename(f)}")

# Write source_items as a 2D (time, stac_item) variable directly via zarr
print("Writing source_items...")
split_ids  = [s.split(",") for s in stac_ids]
max_ids    = max(len(ids) for ids in split_ids)
stac_array = np.array(
    [ids + [""] * (max_ids - len(ids)) for ids in split_ids],
    dtype="S64",
)  # shape: (time, stac_item)

root = zarr.open(OUT_ZARR, mode="a")
arr = root.create_array(
    "source_items",
    shape=stac_array.shape,
    chunks=(1, max_ids),
    dtype="S64",
    overwrite=True,
    dimension_names=["time", "stac_item"],
)
arr[:] = stac_array
root["source_items"].attrs.update({
    "long_name": "STAC item IDs used to generate this mask",
    "description": "From Microsoft Planetary Computer Sentinel-2 L2A STAC catalog",
    "API_URL": "https://planetarycomputer.microsoft.com/api/stac/v1",
})

zarr.consolidate_metadata(OUT_ZARR)
print("Done")
