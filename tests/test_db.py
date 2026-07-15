"""Database (SQLite) 单元测试。"""

from __future__ import annotations

import os
import tempfile

from aisim.db import Database


def test_save_load_json_roundtrip():
    path = os.path.join(tempfile.gettempdir(), "aisim_test.db")
    db = Database(path=path)
    db.connect()
    try:
        db.save_json("k", {"a": 1, "b": [2, 3]})
        assert db.load_json("k") == {"a": 1, "b": [2, 3]}
        assert db.load_json("missing") is None
        # 覆盖
        db.save_json("k", {"a": 2})
        assert db.load_json("k") == {"a": 2}
    finally:
        db.close()
        if os.path.exists(path):
            os.remove(path)


def test_connect_creates_table():
    path = os.path.join(tempfile.gettempdir(), "aisim_test2.db")
    db = Database(path=path)
    db.connect()
    try:
        # 表存在即可写入
        db.save_json("x", 42)
        assert db.load_json("x") == 42
    finally:
        db.close()
        if os.path.exists(path):
            os.remove(path)
