import unittest

from twitter_archive_scraper import (
    Capture,
    parse_cdx_capture_text,
    parse_tweet_capture,
    parse_tweet_html,
    status_id_from_url,
)


class TwitterArchiveScraperTests(unittest.TestCase):
    def test_status_id_from_url(self):
        self.assertEqual(
            status_id_from_url("https://twitter.com/example/status/1234567890"),
            "1234567890",
        )
        self.assertEqual(
            status_id_from_url("https://x.com/example/statuses/987654321"),
            "987654321",
        )

    def test_parse_cdx_capture_text(self):
        text = """
        20200102030405 https://twitter.com/example/status/123
        malformed
        20240102030405 https://x.com/example/status/456?lang=en
        """
        self.assertEqual(
            parse_cdx_capture_text(text),
            [
                ("20200102030405", "https://twitter.com/example/status/123"),
                ("20240102030405", "https://x.com/example/status/456?lang=en"),
            ],
        )

    def test_parse_modern_meta_tweet(self):
        capture = Capture(
            timestamp="20200102030405",
            original="https://twitter.com/example/status/123",
            archive_url="https://web.archive.org/web/20200102030405/https://twitter.com/example/status/123",
            status_id="123",
        )
        raw_html = """
        <html>
          <head>
            <meta property="og:description" content='Example on Twitter: "historic text"'>
            <meta property="article:published_time" content="2020-01-02T03:04:05Z">
            <meta property="og:image" content="https://pbs.twimg.com/media/ABC123.jpg?format=jpg&amp;name=large">
          </head>
        </html>
        """
        tweet = parse_tweet_html(raw_html, capture)
        self.assertEqual(tweet.text, "historic text")
        self.assertEqual(tweet.date, "2020-01-02T03:04:05+00:00")
        self.assertEqual(
            tweet.image_urls,
            ["https://pbs.twimg.com/media/ABC123.jpg?format=jpg&name=large"],
        )

    def test_parse_old_tweet_markup(self):
        capture = Capture(
            timestamp="20130506070809",
            original="https://twitter.com/example/status/456",
            archive_url="https://web.archive.org/web/20130506070809/https://twitter.com/example/status/456",
            status_id="456",
        )
        raw_html = """
        <html>
          <body>
            <p class="tweet-text">Old archive text</p>
            <span data-time-ms="1367824089000"></span>
            <img src="https://web.archive.org/web/20130506070809im_/https://pbs.twimg.com/media/XYZ.png">
          </body>
        </html>
        """
        tweet = parse_tweet_html(raw_html, capture)
        self.assertEqual(tweet.text, "Old archive text")
        self.assertEqual(tweet.date, "2013-05-06T07:08:09+00:00")
        self.assertEqual(tweet.image_urls, ["https://pbs.twimg.com/media/XYZ.png"])

    def test_parse_wayback_twitter_post_json(self):
        capture = Capture(
            timestamp="20240508225115",
            original="https://twitter.com/uwu_underground/status/1788340917495300442",
            archive_url="https://web.archive.org/web/20240508225115/https://twitter.com/uwu_underground/status/1788340917495300442",
            status_id="1788340917495300442",
        )
        raw_json = """
        {
          "data": {
            "id": "1788340917495300442",
            "created_at": "2024-05-08T22:51:15.000Z",
            "text": ".\\u2661 \\u2229_\\u2229 .\\nUwU Crew Please Help",
            "attachments": {"media_keys": ["3_123"]}
          },
          "includes": {
            "media": [
              {
                "media_key": "3_123",
                "type": "photo",
                "url": "https://pbs.twimg.com/media/ABC123.jpg"
              }
            ]
          }
        }
        """
        tweet = parse_tweet_capture(raw_json, capture)
        self.assertEqual(tweet.text, ".♡ ∩_∩ .\nUwU Crew Please Help")
        self.assertEqual(tweet.date, "2024-05-08T22:51:15+00:00")
        self.assertEqual(tweet.image_urls, ["https://pbs.twimg.com/media/ABC123.jpg"])


if __name__ == "__main__":
    unittest.main()
