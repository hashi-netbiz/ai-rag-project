import pytest
from app.rbac.permissions import get_allowed_departments


@pytest.mark.parametrize("role", ["finance", "marketing", "hr", "engineering", "c_level", "employee"])
def test_all_roles_return_non_empty(role):
    assert len(get_allowed_departments(role)) > 0


def test_finance():
    assert get_allowed_departments("finance") == ["finance", "general"]


def test_marketing():
    assert get_allowed_departments("marketing") == ["marketing", "general"]


def test_hr():
    assert get_allowed_departments("hr") == ["hr", "general"]


def test_engineering():
    assert get_allowed_departments("engineering") == ["engineering", "general"]


def test_c_level():
    depts = get_allowed_departments("c_level")
    assert set(depts) == {"finance", "marketing", "hr", "engineering", "general"}


def test_employee():
    assert get_allowed_departments("employee") == ["general"]


def test_unknown_role():
    assert get_allowed_departments("unknown") == []
