from server import app


def test_examples_page_renders():
    client = app.test_client()
    resp = client.get('/demo/examples')
    assert resp.status_code == 200
    assert b'Campaign Example Gallery' in resp.data


def test_preview_uses_preset_content():
    client = app.test_client()
    resp = client.get('/api/v1/demo/preview/acme?preset=vip_launch&first_name=Jamie')
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'VIP early access is open' in body['amp_html']
    assert 'Your early-access window is live' in body['amp_html']
