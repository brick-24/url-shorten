import requests

def test_http_connection():
    response = requests.get("https://google.com", timeout=5)

    assert response.status_code == 200