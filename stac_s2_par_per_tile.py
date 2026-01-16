#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec  9 15:52:59 2025

@author: laserglaciers
"""

import pystac_client
from pystac_client import Client
import rasterio
from rasterio.enums import Resampling
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from multiprocessing import Pool, cpu_count
from rasterio.plot import show
import os

#%%
api_url = "https://earth-search.aws.element84.com/v1"
client = Client.open(api_url)
tile_list_path = './sentinel_2_tiles.csv'
s2_tiles = pd.read_csv(tile_list_path)

date_range = "2021-05-01/2021-08-31" 

# Cloud cover filter: less than 10%
cloud_cover_max = 10 

#%%
def lake_detect(stac_item, tile, save_rgb=False):
    
    
    blue_href = stac_item.assets['blue'].href
    red_href = stac_item.assets['red'].href
    green_href = stac_item.assets['green'].href
    swir_href = stac_item.assets['swir16'].href
    
    
    blue_asset = stac_item.assets['blue']
    scale = blue_asset.extra_fields['raster:bands'][0]['scale']
    offset = blue_asset.extra_fields['raster:bands'][0]['offset']
    upscale_factor = 2
    
    
    item_id = stac_item.id
    print(f'Starting to read: {item_id}')
    with rasterio.open(blue_href, mode='r') as src_b:
        
        blue_band = src_b.read(1).astype(np.float32)
        blue_reflect = blue_band * scale + offset
    
    
    with rasterio.open(red_href, mode='r') as src_r:
        
        red_band = src_r.read(1).astype(np.float32)
        red_reflect = red_band * scale + offset
    
    with rasterio.open(green_href, mode='r') as src_g:
        
        green_band = src_g.read(1).astype(np.float32)
        green_reflect = green_band * scale + offset
        profile = src_g.profile
    
    
    
    with rasterio.open(swir_href, mode='r') as src_sw:
        swir_band = src_sw.read(1, 
                                out_shape=(
                                src_sw.count,
                                int(src_sw.height * upscale_factor),
                                int(src_sw.width * upscale_factor)
                                ),
                                resampling=Resampling.bilinear).astype(np.float64)
        swir_reflect = swir_band * scale + offset
    
    
    print(f'{item_id} in memory')
    
    ndsi = (green_reflect - swir_reflect) / (green_reflect + swir_reflect)
    ndwi = (blue_reflect - red_reflect) / (blue_reflect + red_reflect)
    
    ndsi_mask = ndsi > 0.85
    blue_mask = blue_reflect > 0.1 
    ndwi_mask = ndwi > 0.3 # 0.5 is dunmire 2021 value
    
    combined_mask = blue_mask & ndsi_mask & ndwi_mask
    # ndwi_filter_masked = np.where(combined_mask, ndwi, np.nan)
    # ndwi_filter = np.where(ndwi>=0.5, ndwi ,np.nan)
    lake_pixels = np.where(combined_mask, ndwi, np.nan)
    
    profile_lake_pixels = profile.copy()
    profile_lake_pixels['dtype'] = 'int8'
    lake_pixels_zero_binary = np.where(np.isnan(lake_pixels), 0, 1)
    
    

    print(f'saving binary mask: {item_id}')
    out_dir = f'./lake_detection_binary_masks_parallel/{tile}/'
    os.makedirs(out_dir, exist_ok=True)
    out_file = f'./{out_dir}{item_id}_lake_pixels.tif'
    
    
    with rasterio.open(f'./{out_file}', mode='w', **profile_lake_pixels) as dst:
        dst.write(lake_pixels_zero_binary, 1)

    if save_rgb:
        rgb_bands = [red_reflect, green_reflect, blue_reflect]
        rbg_names = ['red', 'green', 'blue']
        
        
        profile_rgb = profile.copy()
        profile_rgb['count'] = 3
        profile_rgb['dtype'] = 'float32'
        
        
        rgb_out_dir = f'./lake_detection_rgb_parallel/{tile}/'
        os.makedirs(rgb_out_dir, exist_ok=True)
        rgb_out = f'./{rgb_out_dir}{item_id}_rgb.tif'
        
        print(f'saving rgb: {item_id}')
        with rasterio.open(f'{rgb_out}', mode='w', **profile_rgb) as dst:
            for band_num, band in enumerate(rgb_bands):
                
                dst.write(band, band_num+1) # Write the data to band 1
                dst.set_band_description(band_num+1, rbg_names[band_num])


    return 



#%%
for tile in s2_tiles['tile']:
    
    search_results = client.search(
        collections=["sentinel-2-c1-l2a"], #sentinel-2-l1c sentinel-2-c1-l2a sentinel-2-l2a
        # intersects=point,
        datetime=date_range,
        query={"eo:cloud_cover": {"lt": cloud_cover_max},
              "grid:code": {"eq":f"MGRS-{tile}"} },
        sortby=["-properties.datetime", "+id"],
    )
    
    items = list(search_results.items())
    print(f"Found: {len(items):d} datasets")
    
    tile_list = [tile]*len(items)
    items_zip = list(zip(items, tile_list))
    
    if __name__ == '__main__':
        
        with Pool(processes=cpu_count()) as pool:
            
            # pool.map automatically distributes each item in 'data' to worker_function
            results = pool.startmap(lake_detect, items_zip)