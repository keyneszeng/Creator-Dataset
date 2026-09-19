from app.platforms.xiaohongshu.comments import extract_picture_urls


def test_extract_picture_urls_from_nested_structures() -> None:
    pictures = [
        {
            "info_list": [
                {"url": "https://img.example/a.jpg"},
                {"url_pre": "https://img.example/a-preview.jpg"},
            ]
        },
        {"url_default": "https://img.example/b.jpg"},
    ]

    urls = extract_picture_urls(pictures)

    assert urls == [
        "https://img.example/a.jpg",
        "https://img.example/a-preview.jpg",
        "https://img.example/b.jpg",
    ]
