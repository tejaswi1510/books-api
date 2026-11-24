BASE = "/api/v1/books"

NEW_BOOK = {
    "title": "The Left Hand of Darkness",
    "author": "Ursula K. Le Guin",
    "genre": "Science Fiction",
    "published_year": 1969,
    "price": 11.99,
    "in_stock": True,
}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_list_books_default_pagination(client):
    body = client.get(BASE).json()
    assert body["total"] == 12
    assert len(body["items"]) == 12
    assert body["limit"] == 20


def test_list_filter_and_sort(client):
    body = client.get(BASE, params={"genre": "technology", "sort_by": "price", "order": "desc"}).json()
    assert body["total"] == 3
    assert body["items"][0]["title"] == "Designing Data-Intensive Applications"


def test_list_search_and_pagination(client):
    assert client.get(BASE, params={"search": "orwell"}).json()["total"] == 1
    page = client.get(BASE, params={"limit": 5, "offset": 10}).json()
    assert len(page["items"]) == 2 and page["total"] == 12


def test_get_book_and_404(client):
    assert client.get(f"{BASE}/3").json()["title"] == "Dune"
    resp = client.get(f"{BASE}/999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "book_not_found"


def test_create_book(client):
    resp = client.post(BASE, json=NEW_BOOK)
    assert resp.status_code == 201
    assert resp.json()["id"] == 13
    assert resp.headers["location"].endswith("/api/v1/books/13")
    assert client.get(f"{BASE}/13").status_code == 200


def test_create_validation_error(client):
    resp = client.post(BASE, json={**NEW_BOOK, "price": -1})
    assert resp.status_code == 422


def test_put_replaces_book(client):
    resp = client.put(f"{BASE}/1", json=NEW_BOOK)
    assert resp.status_code == 200
    assert resp.json()["title"] == NEW_BOOK["title"]
    assert client.put(f"{BASE}/999", json=NEW_BOOK).status_code == 404


def test_patch_updates_only_given_fields(client):
    resp = client.patch(f"{BASE}/1", json={"price": 5.0})
    body = resp.json()
    assert resp.status_code == 200
    assert body["price"] == 5.0
    assert body["title"] == "1984"


def test_patch_rejects_explicit_null(client):
    resp = client.patch(f"{BASE}/1", json={"title": None})
    assert resp.status_code == 422


def test_delete_book(client):
    assert client.delete(f"{BASE}/1").status_code == 204
    assert client.get(f"{BASE}/1").status_code == 404
    assert client.delete(f"{BASE}/1").status_code == 404
