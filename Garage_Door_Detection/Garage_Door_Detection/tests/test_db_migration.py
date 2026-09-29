from sqlalchemy import create_engine, inspect, text

import app.db.init_db as init_db_module


def test_vehicle_label_migration_preserves_existing_door_labels(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE training_crops ("
                "id INTEGER PRIMARY KEY, label VARCHAR(20), label_source VARCHAR(20))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO training_crops (id, label, label_source) "
                "VALUES (1, 'open', 'manual'), (2, 'closed', 'batch')"
            )
        )

    monkeypatch.setattr(init_db_module, "engine", engine)
    init_db_module._add_vehicle_label_columns()
    init_db_module._add_vehicle_label_columns()

    columns = {column["name"] for column in inspect(engine).get_columns("training_crops")}
    assert {"vehicle_label", "vehicle_label_source", "vehicle_labeled_at"} <= columns
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT label, label_source, vehicle_label, vehicle_label_source "
                "FROM training_crops ORDER BY id"
            )
        ).all()
    assert rows == [("open", "manual", None, None), ("closed", "batch", None, None)]
