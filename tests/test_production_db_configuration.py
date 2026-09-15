"""
Tests for Prompt 9: Production Database Configuration and Dual-Mode Engine Management.
Verifies configurable pool settings, failover controls, and offline SQLite compatibility.
"""
import os
import unittest
from unittest.mock import patch, MagicMock


class TestProductionDatabaseConfiguration(unittest.TestCase):
    def test_database_config_offline_sqlite(self):
        """Verify default offline SQLite configuration returns correct metadata."""
        from backend.app.database import get_database_config, is_sqlite

        config = get_database_config()
        self.assertIn("dialect", config)
        self.assertIn("offline_mode", config)
        self.assertIn("database_path", config)
        if is_sqlite:
            self.assertEqual(config["dialect"], "sqlite")
            self.assertTrue(config["offline_mode"])
            self.assertTrue(config["database_path"].endswith("school.db"))

    def test_postgresql_pool_configuration_parameters(self):
        """Verify PostgreSQL pool settings can be configured via environment variables."""
        with patch.dict(os.environ, {
            "DB_POOL_SIZE": "35",
            "DB_MAX_OVERFLOW": "20",
            "DB_POOL_TIMEOUT": "45",
            "DB_POOL_RECYCLE": "900",
            "DB_CONNECT_TIMEOUT": "15"
        }):
            import importlib
            import backend.app.database as db_mod
            importlib.reload(db_mod)

            self.assertEqual(db_mod.DB_POOL_SIZE, 35)
            self.assertEqual(db_mod.DB_MAX_OVERFLOW, 20)
            self.assertEqual(db_mod.DB_POOL_TIMEOUT, 45)
            self.assertEqual(db_mod.DB_POOL_RECYCLE, 900)
            self.assertEqual(db_mod.DB_CONNECT_TIMEOUT, 15)

    def test_production_postgresql_failure_raises_runtime_error(self):
        """In production mode with postgres URL, connection failure must raise RuntimeError unless fallback enabled."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://user:pass@127.0.0.1:5432/nonexistent_db",
            "DB_ALLOW_SQLITE_FALLBACK": "false"
        }):
            import importlib
            import backend.app.database as db_mod
            with patch("backend.app.database.create_engine") as mock_create_engine:
                mock_engine = MagicMock()
                mock_engine.connect.side_effect = Exception("Connection refused")
                mock_create_engine.return_value = mock_engine

                with self.assertRaises(RuntimeError) as ctx:
                    db_mod._init_resilient_engine()
                self.assertIn("PostgreSQL connection failed in production mode", str(ctx.exception))

    def test_production_postgresql_failure_allows_explicit_fallback(self):
        """If DB_ALLOW_SQLITE_FALLBACK is set to true in production, it falls back to SQLite."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://user:pass@127.0.0.1:5432/nonexistent_db",
            "DB_ALLOW_SQLITE_FALLBACK": "true"
        }):
            import importlib
            import backend.app.database as db_mod
            with patch("backend.app.database.create_engine") as mock_create_engine:
                # First call is PostgreSQL attempt (which fails), second is fallback to SQLite
                mock_pg_engine = MagicMock()
                mock_pg_engine.connect.side_effect = Exception("Connection refused")
                mock_sqlite_engine = MagicMock()

                mock_create_engine.side_effect = [mock_pg_engine, mock_sqlite_engine]
                result_engine = db_mod._init_resilient_engine()
                self.assertEqual(result_engine, mock_sqlite_engine)

    def test_dispose_engine_callable(self):
        """Verify dispose_engine executes cleanly without crashing."""
        from backend.app.database import dispose_engine
        dispose_engine()  # Should complete cleanly


if __name__ == "__main__":
    unittest.main()
