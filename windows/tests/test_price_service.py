from justincard.price_service import estimate_price


CARD = {
    "id": 6983839,
    "card_sets": [
        {"set_code": "BLRR-EN084", "set_name": "Battles of Legend", "set_rarity": "Secret Rare", "set_price": "10.00"},
        {"set_code": "DUDE-EN019", "set_name": "Duel Devastator", "set_rarity": "Ultra Rare", "set_price": "2.00"},
    ],
    "card_prices": [{"cardmarket_price": "1.50"}],
}


def test_price_is_print_rarity_and_condition_specific_offline():
    nm = estimate_price(CARD, print_code="BLRR-EN084", rarity="Secret Rare", language="en", condition="Near Mint", live=False)
    played = estimate_price(CARD, print_code="BLRR-EN084", rarity="Secret Rare", language="en", condition="Played", live=False)
    assert nm.print_price_usd == 10.0
    assert nm.rarity == "Secret Rare"
    assert nm.amount_eur == 7.5
    assert played.amount_eur == 4.12
    assert played.condition_factor == 0.55
    assert "Cardmarket-Referenzpreis" in nm.note
    assert "Cardmarket" in nm.source


def test_language_fallback_is_explicit_for_unsupported_api_language():
    result = estimate_price(CARD, print_code="BLRR-JP084", rarity="Secret Rare", language="ja", condition="Near Mint", live=False)
    assert result.requested_language == "ja"
    assert result.resolved_language == "en"
    assert "Fallback" in result.note
