from server import app


def test_admin_dashboard_renders():
    client = app.test_client()
    response = client.get('/demo/admin')
    assert response.status_code == 200
    assert b'Demo Operator Dashboard' in response.data


def test_admin_create_requires_recipients():
    client = app.test_client()
    response = client.post(
        '/demo/admin/campaigns/create',
        data={
            'brand_id': 'acme',
            'name': 'Admin test',
            'subject': 'Subj',
            'from_email': 'demo@example.com',
            'reply_to': 'demo@example.com',
            'recipients': '',
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert '/demo/admin?error=' in response.headers['Location']
