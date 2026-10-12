import requests

from slg.mapillary import chunk_bbox, fetch_features, sign_mph


def test_sign_mph():
    assert sign_mph("regulatory--maximum-speed-limit-30--g1") == 30
    assert sign_mph("regulatory--maximum-speed-limit-20--g3") == 20
    assert sign_mph("regulatory--end-of-maximum-speed-limit-30--g1") is None
    assert sign_mph("regulatory--no-entry--g1") is None


def test_chunk_bbox_covers_area():
    cells = chunk_bbox((-0.37, 51.04, -0.29, 51.09), step=0.05)
    assert len(cells) == 2 * 1
    assert cells[0][:2] == (-0.37, 51.04)
    assert max(c[2] for c in cells) == -0.29 and max(c[3] for c in cells) == 51.09


class _Resp:
    def __init__(self, data=None, fail=False):
        self._data, self._fail = data, fail

    def raise_for_status(self):
        if self._fail:
            raise requests.HTTPError("500")

    def json(self):
        return {"data": self._data}


class _Session:
    """First call fails, later calls return one speed and one non-speed feature."""
    def __init__(self):
        self.n = 0

    def get(self, *a, **k):
        self.n += 1
        if self.n == 1:
            return _Resp(fail=True)
        return _Resp([{"id": "1", "object_value": "regulatory--maximum-speed-limit-30--g1"},
                      {"id": "2", "object_value": "regulatory--no-entry--g1"}])


def test_fetch_features_survives_failed_cell():
    feats, failed = fetch_features((-0.37, 51.04, -0.29, 51.09), "tok",
                                   session=_Session(), pause=0)
    assert failed == 1
    assert [f["id"] for f in feats] == ["1"]
