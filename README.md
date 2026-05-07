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

