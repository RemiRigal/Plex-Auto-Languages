import time
import pytest
import requests

from plex_auto_languages.utils.healthcheck import HealthcheckServer


def always_true():
    return True


def always_false():
    return False


def test_healthcheck():
    server = HealthcheckServer("test", always_false, always_false)
    server.start()
    time.sleep(1)

    response = requests.get("http://localhost:9880/")
    assert response.status_code == 400
    assert response.json()["healthy"] is False

    response = requests.get("http://localhost:9880/health")
    assert response.status_code == 400
    assert response.json()["healthy"] is False

    response = requests.get("http://localhost:9880/ready")
    assert response.status_code == 400
    assert response.json()["ready"] is False

    server.shutdown()
    time.sleep(1)

    server = HealthcheckServer("test2", always_true, always_false)
    server.start()
    time.sleep(1)

    response = requests.get("http://localhost:9880/")
    assert response.status_code == 400
    assert response.json()["healthy"] is False

    response = requests.get("http://localhost:9880/health")
    assert response.status_code == 400
    assert response.json()["healthy"] is False

    response = requests.get("http://localhost:9880/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True

    server.shutdown()
    time.sleep(1)

    server = HealthcheckServer("test3", always_true, always_true)
    server.start()
    time.sleep(1)

    response = requests.get("http://localhost:9880/")
    assert response.status_code == 200
    assert response.json()["healthy"] is True

    response = requests.get("http://localhost:9880/health")
    assert response.status_code == 200
    assert response.json()["healthy"] is True

    response = requests.get("http://localhost:9880/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True

    server.shutdown()
    time.sleep(2)

    with pytest.raises(requests.exceptions.ConnectionError):
        response = requests.get("http://localhost:9880/")
        print(response.status_code)
        print(response.json())
