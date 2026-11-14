"""A0 iskelet testleri (rev.3): veritabanı gerektirmez."""
import importlib.util
from pathlib import Path

import pytest

from app.db.base import SCHEMAS, Base

ROOT = Path(__file__).parents[2]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alti_sema_var():
    assert SCHEMAS == ("core", "behavioral", "sans", "anomaly", "ops", "evaluation")


def test_tek_metadata():
    assert Base.metadata.naming_convention["pk"] == "PK_%(table_name)s"


def test_yalniz_iki_servis_rolu_var_sans_rolu_yok():
    m = _load("migrations/versions/0001_schemas_and_roles.py", "m0001")
    assert m.ROLES == {"astra_app_role": "astra_app", "astra_eval_role": "astra_eval"}


def test_api_evaluation_a_erisemez():
    m = _load("migrations/versions/0001_schemas_and_roles.py", "m0001")
    assert "evaluation" in m.DENIES["astra_app_role"]
    assert "astra_eval_role" not in m.DENIES


def test_bootstrap_sans_hesabi_olusturmaz():
    b = _load("scripts/bootstrap.py", "bootstrap")
    assert set(b.SERVICE_LOGINS) == {"astra_app", "astra_eval"}


@pytest.mark.parametrize("bad", ["Astra;DROP", "a b", "x]", "", "1abc"])
def test_bootstrap_guvensiz_adi_reddeder(bad):
    b = _load("scripts/bootstrap.py", "bootstrap")
    with pytest.raises(ValueError):
        b.safe_name(bad)


def test_bootstrap_odbc_ozel_karakterleri_kacirir():
    b = _load("scripts/bootstrap.py", "bootstrap")
    assert b.odbc_value("a;b}c") == "{a;b}}c}"


def test_bootstrap_password_policy():
    bootstrap = _load("scripts/bootstrap.py", "bootstrap")
    assert bootstrap.password_problem("App-Astra2026x") is None
    assert bootstrap.password_problem("Abc12!") == "en az 8 karakter olmalı"
    assert "en az üçünü" in bootstrap.password_problem("astrapassword")
    assert bootstrap.password_problem("astra-2026x") is None  # küçük + rakam + sembol
