from unittest.mock import patch

from tests.helpers import create_ctfd, destroy_ctfd, gen_user, register_user


def test_ratelimit_on_auth():
    """Test that ratelimiting function works properly"""
    app = create_ctfd()
    with app.app_context():
        register_user(app)
        with app.test_client() as client:
            r = client.get("/login")
            with client.session_transaction() as sess:
                data = {
                    "name": "user",
                    "password": "wrong_password",
                    "nonce": sess.get("nonce"),
                }
            for _ in range(10):
                r = client.post("/login", data=data)
                assert r.status_code == 200

            for _ in range(5):
                r = client.post("/login", data=data)
                assert r.status_code == 429
    destroy_ctfd(app)


def test_ratelimit_login_isolated_by_identity():
    """Users behind the same IP do not share login rate limit buckets"""
    app = create_ctfd()
    with app.app_context():
        gen_user(app.db, name="user1", email="user1@examplectf.com")
        gen_user(app.db, name="user2", email="user2@examplectf.com")
        with app.test_client() as client:
            client.get("/login")
            with client.session_transaction() as sess:
                nonce = sess.get("nonce")
            data1 = {
                "name": "user1",
                "password": "wrong_password",
                "nonce": nonce,
            }
            data2 = {
                "name": "user2",
                "password": "wrong_password",
                "nonce": nonce,
            }
            for _ in range(10):
                r = client.post("/login", data=data1)
                assert r.status_code == 200

            r = client.post("/login", data=data1)
            assert r.status_code == 429

            r = client.post("/login", data=data2)
            assert r.status_code == 200
    destroy_ctfd(app)


def test_ratelimit_login_ip_guard():
    """Per-IP guard limits login attempts across many usernames"""
    app = create_ctfd()
    with app.app_context():
        with patch.dict(
            "CTFd.utils.decorators.AUTH_IP_GUARD",
            {"auth.login": (5, 60)},
        ):
            with app.test_client() as client:
                client.get("/login")
                with client.session_transaction() as sess:
                    nonce = sess.get("nonce")
                for i in range(5):
                    data = {
                        "name": "user{}".format(i),
                        "password": "wrong_password",
                        "nonce": nonce,
                    }
                    r = client.post("/login", data=data)
                    assert r.status_code == 200

                data = {
                    "name": "user5",
                    "password": "wrong_password",
                    "nonce": nonce,
                }
                r = client.post("/login", data=data)
                assert r.status_code == 429
    destroy_ctfd(app)


def test_ratelimit_reset_password_isolated_by_token():
    """Users behind the same IP do not share reset token validation rate limit buckets"""
    app = create_ctfd()
    with app.app_context():
        token1 = "a" * 64
        token2 = "b" * 64
        with app.test_client() as client:
            client.get("/reset_password/{}".format(token1))
            with client.session_transaction() as sess:
                nonce = sess.get("nonce")
            data1 = {"nonce": nonce, "password": "short"}

            for _ in range(10):
                r = client.post("/reset_password/{}".format(token1), data=data1)
                assert r.status_code == 200

            r = client.post("/reset_password/{}".format(token1), data=data1)
            assert r.status_code == 429

            client.get("/reset_password/{}".format(token2))
            with client.session_transaction() as sess:
                nonce = sess.get("nonce")
            data2 = {"nonce": nonce, "password": "short"}
            r = client.post("/reset_password/{}".format(token2), data=data2)
            assert r.status_code == 200
    destroy_ctfd(app)
