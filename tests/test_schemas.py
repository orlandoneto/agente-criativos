from app.schemas import LegendaResult


def test_hashtags_ganham_cerquilha():
    r = LegendaResult(
        gancho="Oi",
        corpo="Corpo",
        cta="CTA",
        hashtags=["pme", "#tech", "  processo "],
    )
    assert r.hashtags == ["#pme", "#tech", "#processo"]
