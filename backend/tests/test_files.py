import io
from urllib.request import Request

from dga.shared.files import S3CompatibleFileStore


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_s3_adapter_get_signs_request_and_returns_bytes(monkeypatch):
    captured = {}

    def fake_open(request: Request, timeout):
        captured['request'] = request
        captured['timeout'] = timeout
        return FakeResponse(b'pdf bytes')

    monkeypatch.setattr('dga.shared.files.urlopen', fake_open)
    store = S3CompatibleFileStore(
        'http://object-store:9000', 'dga-lab', 'access', 'secret'
    )

    content = store.get(object_key='laboratory/reports/a report.pdf')

    assert content == b'pdf bytes'
    assert captured['request'].method == 'GET'
    assert captured['request'].full_url.endswith('/dga-lab/laboratory/reports/a%20report.pdf')
    assert captured['timeout'] == 10
