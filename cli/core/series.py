"""Per-scene AOI time series pulled from Earth Engine."""
import ee


def series_getinfo(image_collection, band, aoi_geom, scale=10):
    """(date, AOI-mean of band) for every image, sorted by date; images
    whose AOI is fully masked are skipped."""
    def to_feature(img):
        value = img.select(band).reduceRegion(
            ee.Reducer.mean(), aoi_geom, scale, maxPixels=1e10, tileScale=4
        ).get(band)
        return ee.Feature(None, {"date": img.date().format("YYYY-MM-dd"), "value": value})

    features = ee.FeatureCollection(image_collection.map(to_feature)).getInfo()
    out = []
    for f in features["features"]:
        props = f["properties"]
        if props.get("value") is not None:
            out.append((props["date"], props["value"]))
    return sorted(out, key=lambda t: t[0])


def water_fraction_series(collection, classify, aoi_geom, scale=10):
    """Fraction of the AOI classified as water, per scene."""
    flags = collection.map(lambda img: classify(img).copyProperties(img, ["system:time_start"]))
    return series_getinfo(flags, "is_water", aoi_geom, scale)
