from agressivo.exchange.balance import base_asset_from_symbol


def test_base_asset_from_symbol() -> None:
    assert base_asset_from_symbol("BTC/USDT") == "BTC"
    assert base_asset_from_symbol("ETH/USDT:USDT") == "ETH"
