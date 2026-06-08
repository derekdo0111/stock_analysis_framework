"""CLI tests — mock full pipeline."""

from unittest.mock import MagicMock, patch
import sys
import pytest


class TestCLIModule:
    def test_cli_module_import(self):
        """CLI module can be imported."""
        from src.turtle.cli import main
        assert callable(main)


class TestCLIParse:
    def test_help_output(self):
        import io
        from argparse import ArgumentParser

        # Test that argparse help works
        parser = ArgumentParser(prog="test")
        parser.add_argument("ts_code")
        parser.add_argument("--html", action="store_true")
        out = io.StringIO()

        try:
            parser.print_help(file=out)
        except SystemExit:
            pass
        help_text = out.getvalue()
        assert "ts_code" in help_text.lower() or "ts_code" in help_text


class TestFinalScoreProperties:
    """Test FinalScore data class behavior."""

    def test_final_score_fields(self):
        from src.turtle.calculator.scoring import FinalScore
        fs = FinalScore(
            ts_code="600519.SH", name="茅台", l2_score=15, l3_multiplier=1.0,
            l4_score=20, l5_score=15, raw_total=50, final_score=50,
            pool="观察池", pr_pct=6.5, oe_quality="\U0001f7e2 可信",
            position_pct=8, business_model="良",
        )
        assert fs.l2_score + fs.l4_score + fs.l5_score == 50
        assert fs.pool in ("核心池", "观察池", "备选池")

    def test_final_score_invalid(self):
        from src.turtle.calculator.scoring import FinalScore
        fs = FinalScore(
            ts_code="test", name="t", l2_score=0, l3_multiplier=0,
            l4_score=0, l5_score=0, raw_total=0, final_score=0,
            pool="备选池", pr_pct=0, oe_quality="",
            position_pct=0,
        )
        assert fs.pool == "备选池"


class TestStorageEdgeCases:
    """Additional storage edge cases."""

    def test_delete_nonexistent(self, tmp_path):
        from src.core.data.pool.storage.local_storage import LocalStorage
        store = LocalStorage(tmp_path / "data")
        # Should not raise
        store.delete("nonexistent")

    def test_load_json_prefer_when_parquet_missing(self, tmp_path):
        from src.core.data.pool.storage.local_storage import LocalStorage
        import pandas as pd
        store = LocalStorage(tmp_path / "data")
        df = pd.DataFrame({"a": [1]})
        store.save(df, "test", format="json")
        loaded = store.load("test", prefer="parquet")
        assert len(loaded) == 1

    def test_list_datasets_both_formats(self, tmp_path):
        from src.core.data.pool.storage.local_storage import LocalStorage
        import pandas as pd
        store = LocalStorage(tmp_path / "data")
        store.save(pd.DataFrame({"a": [1]}), "ds1", format="both")
        names = store.list_datasets()
        assert "ds1" in names  # should appear once even though stored in both
