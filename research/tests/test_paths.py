from slg.paths import ROOT, DATA, RESULTS


def test_root_is_repo_root():
    assert (ROOT / "Speed Limit Estimator Plan.md").exists()
    assert DATA == ROOT / "data"
    assert RESULTS == ROOT / "results"
