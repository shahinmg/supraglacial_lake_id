# supraglacial_lake_id


A pipeline for NDWI masking for supraglacial lakes in central-west Greenland using Sentinel-2 L2A imagery from Microsoft Planetary Computer. The final output are Zarr stores for a particular year's melt season.

The pipeline works as follows
```
lake_detect_parallel.py
↓
output_dir/
↓
merge_daily_masks.py
↓
lake_detection_binary_masks_merged_daily_v2/
↓
reproject_to_3413.py &larr; NSIDC-0793_*.nc (ice mask)
↓
output_dir/
↓
create_zarr_datacube.py
↓
lake_detection_binary_masks_.zarr
```

The `reading_zarr_and_item_grab.ipynb` in the `notebooks/` dir has an example on how to read the zarr and grab one of the stac item's assets used for a single time step.

Zarr dimensions are: (time: num_of_days, x: 26088y: 52904, stac_item: 9). The `stac_item` dim refers to the number of MRGS tiles in CW Greenland found in the `sentinel_2_tiles.csv`
