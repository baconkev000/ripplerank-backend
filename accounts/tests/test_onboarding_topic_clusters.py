from accounts.onboarding_topic_clusters import build_topic_clusters


def test_topic_clusters_match_headings_to_ranked():
    pages = [
        {
            "url": "https://example.com/plumbing/",
            "h1": "Emergency plumbing services",
            "h2_h3_headings": ["H2: Drain cleaning"],
            "faq_questions": [],
            "primary_keyword_candidates": ["plumber"],
        },
    ]
    ranked_items = [
        {
            "keyword_data": {
                "keyword": "emergency plumber near me",
                "keyword_info": {"search_volume": 5000},
            },
            "rank_absolute": 4,
        },
        {
            "keyword_data": {
                "keyword": "unrelated cryptocurrency tips",
                "keyword_info": {"search_volume": 100},
            },
            "rank_absolute": 50,
        },
    ]
    out = build_topic_clusters(pages, ranked_items, match_threshold=0.08)
    assert out["crawl_topic_seeds"]
    clusters = out["topic_clusters"]["clusters"]
    assert clusters
    top = clusters[0]
    kws = [r["keyword"] for r in top["ranked_keywords"]]
    assert "emergency plumber near me" in kws
    un = out["topic_clusters"]["unclustered_ranked_keywords"]
    assert any("unrelated" in r["keyword"] for r in un)
