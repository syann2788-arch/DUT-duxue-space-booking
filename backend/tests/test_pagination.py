from datetime import date, timedelta

from tests.conftest import auth_header


def _login(client, student_id: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"student_id": student_id, "password": password})
    assert response.status_code == 200, response.text
    return auth_header(response.json()["access_token"])


def test_list_endpoints_return_bounded_page_metadata(client):
    admin = _login(client, "admin001", "admin123")

    users = client.get("/api/admin/users?limit=2&offset=0", headers=admin)
    assert users.status_code == 200, users.text
    user_page = users.json()
    assert set(user_page) == {"items", "total", "limit", "offset", "has_more"}
    assert len(user_page["items"]) <= 2
    assert user_page["limit"] == 2
    assert user_page["offset"] == 0
    assert user_page["has_more"] == (len(user_page["items"]) < user_page["total"])

    reservations = client.get("/api/admin/reservations?limit=2&offset=0", headers=admin)
    assert reservations.status_code == 200, reservations.text
    reservation_page = reservations.json()
    assert set(reservation_page) == {"items", "total", "limit", "offset", "has_more"}
    assert len(reservation_page["items"]) <= 2

    cleanup = client.get("/api/admin/cleanup?limit=2&offset=0", headers=admin)
    assert cleanup.status_code == 200, cleanup.text
    assert set(cleanup.json()) == {"items", "total", "limit", "offset", "has_more"}


def test_my_reservations_pagination_is_stable(client):
    registered = client.post("/api/auth/register", json={
        "student_id": "20269991",
        "name": "分页测试",
        "phone": "13900009991",
        "class_name": "2599",
        "password": "page1234",
    })
    assert registered.status_code == 200, registered.text
    student = auth_header(registered.json()["access_token"])

    for index in range(3):
        photo = client.post(
            "/api/reservations/campus-card-photo",
            headers=student,
            files={"file": (f"card-{index}.jpg", b"\xff\xd8\xff\xe0page-test", "image/jpeg")},
        )
        assert photo.status_code == 201, photo.text
        created = client.post("/api/reservations", headers=student, json={
            "scene": "study",
            "date": (date.today() + timedelta(days=index + 1)).isoformat(),
            "start_slot": 2,
            "end_slot": 3,
            "people_count": 1,
            "purpose": "个人自习",
            "campus_card_media_id": photo.json()["media_id"],
        })
        assert created.status_code == 201, created.text

    first = client.get("/api/reservations/my?limit=2&offset=0", headers=student).json()
    second = client.get("/api/reservations/my?limit=2&offset=2", headers=student).json()
    pending = client.get(
        "/api/reservations/my?status_filter=pending&limit=2&offset=0", headers=student
    ).json()
    assert first["total"] == 3
    assert first["has_more"] is True
    assert second["has_more"] is False
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1
    assert not ({item["id"] for item in first["items"]} & {item["id"] for item in second["items"]})
    assert pending["total"] == 3
    assert all(item["status"] == "pending" for item in pending["items"])


def test_pagination_limits_are_validated(client):
    admin = _login(client, "admin001", "admin123")
    assert client.get("/api/admin/users?limit=101", headers=admin).status_code == 422
    assert client.get("/api/admin/reservations?offset=-1", headers=admin).status_code == 422
