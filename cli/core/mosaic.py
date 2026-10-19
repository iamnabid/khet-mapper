import ee


def daily_mosaic(collection):
    """One image per calendar day. Large AOIs span several S1 frames or S2
    tiles acquired the same day; measured separately, each partial footprint
    would count as a whole-AOI observation of that date."""
    days = collection.aggregate_array("system:time_start").map(
        lambda t: ee.Date(t).format("YYYY-MM-dd")
    ).distinct()

    def mosaic(day):
        start = ee.Date(day)
        return (
            collection.filterDate(start, start.advance(1, "day"))
            .mosaic()
            .set("system:time_start", start.millis())
        )

    return ee.ImageCollection(days.map(mosaic))
