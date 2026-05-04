import os

import veritabani


def test_default_db_path_is_absolute_and_points_to_project_data_dir():
    assert os.path.isabs(veritabani.DB_NAME)
    assert veritabani.DB_NAME.endswith(os.path.join("data", "solar_log.db"))
    assert os.path.dirname(veritabani.DB_NAME) == os.path.join(veritabani.BASE_DIR, "data")
