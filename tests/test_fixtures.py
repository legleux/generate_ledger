def test_accounts_factory_default(accounts_factory):
    accs = accounts_factory()
    assert len(accs) == 3
    assert all("address" in a for a in accs)


def test_accounts_factory_random(accounts_factory):
    a = accounts_factory(2, mode="random")
    b = accounts_factory(2, mode="random")
    assert len(a) == len(b) == 2
    assert a != b  # probabilistic, add seed if you want determinism
