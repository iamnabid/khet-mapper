import ee

import config


def get_s1_collection(aoi, start, end, orbit="DESCENDING"):
    # GEE's S1_GRD collection already applies thermal-noise removal,
    # radiometric calibration and SRTM terrain correction, and already
    # returns backscatter in dB — do not reapply 10*log10() here.
    return (
        ee.ImageCollection(config.S1_COLLECTION)
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("orbitProperties_pass", orbit))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select(["VV", "VH"])
    )


def _speckle_filter(image, radius_m=config.SPECKLE_FILTER_RADIUS_M):
    return image.focal_median(radius_m, "circle", "meters").copyProperties(
        image, ["system:time_start"]
    )


def get_s1_composite(aoi, start, end, orbit="DESCENDING"):
    collection = get_s1_collection(aoi, start, end, orbit)
    filtered = collection.map(_speckle_filter)
    return filtered, filtered.median().clip(aoi)
