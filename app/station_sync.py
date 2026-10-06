from sqlalchemy import select

from app.station_models import StationObservation, WeatherStation


def save_station(db, values):
    item = db.get(WeatherStation, values["code"])
    if item is None:
        item = WeatherStation(**values)
        db.add(item)
    else:
        for key, value in values.items():
            # A historical export without metadata must not erase the live catalog.
            if value is not None and not (key == "name" and value == values["code"]):
                setattr(item, key, value)
    db.flush()
    return item


def save_observations(db, rows):
    """Idempotent natural key; the caller owns the transaction."""
    inserted = updated = 0
    for meta, values in rows:
        save_station(db, meta)
        item = db.scalar(
            select(StationObservation).where(
                StationObservation.station_code == values["station_code"],
                StationObservation.observed_at == values["observed_at"],
                StationObservation.period == values["period"],
            )
        )
        if item is None:
            db.add(StationObservation(**values))
            inserted += 1
        else:
            for key, value in values.items():
                if value is not None:
                    setattr(item, key, value)
            updated += 1
        db.flush()
    return inserted, updated
