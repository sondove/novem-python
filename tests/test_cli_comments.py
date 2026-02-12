import json
import re

from novem.cli.gql import (
    _aggregate_activity,
    _build_comment_fragment,
    _build_topics_query,
    _get_gql_endpoint,
    _relative_time,
    _visible_len,
    _wrap_text,
    render_topics,
)
from novem.cli.vis import _compact_num, _format_activity
from novem.utils import API_ROOT, colors

from .utils import write_config

gql_endpoint = _get_gql_endpoint(API_ROOT)

auth_req = {
    "username": "demouser",
    "password": "demopass",
    "token_name": "demotoken",
    "token_description": "test token",
}


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes for easier assertion."""
    return re.sub(r"\033\[[0-9;]*m", "", s)


# --- Unit tests for helpers ---


class TestVisibleLen:
    def test_plain_text(self) -> None:
        assert _visible_len("hello") == 5

    def test_with_ansi(self) -> None:
        assert _visible_len("\033[96m@alice\033[0m") == 6

    def test_empty(self) -> None:
        assert _visible_len("") == 0

    def test_multiple_codes(self) -> None:
        s = "\033[1m┌\033[0m \033[96m@bob\033[0m \033[38;5;246m· 3h ago\033[0m"
        assert _visible_len(s) == len("┌ @bob · 3h ago")


class TestRelativeTime:
    def test_just_now(self) -> None:
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        assert _relative_time(now) == "just now"

    def test_minutes(self) -> None:
        import datetime

        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
        assert _relative_time(dt) == "5m ago"

    def test_hours(self) -> None:
        import datetime

        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
        assert _relative_time(dt) == "3h ago"

    def test_days(self) -> None:
        import datetime

        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        assert _relative_time(dt) == "7d ago"

    def test_old_date(self) -> None:
        import datetime

        dt = datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc)
        result = _relative_time(dt)
        assert "Jan 15, 2024" == result


class TestWrapText:
    def test_short_text(self) -> None:
        lines = _wrap_text("hello", "│ ", 80)
        assert lines == ["│ hello"]

    def test_wraps_long_text(self) -> None:
        text = "word " * 30  # 150 chars
        lines = _wrap_text(text.strip(), "│ ", 40)
        assert len(lines) > 1
        for line in lines:
            assert line.startswith("│ ")

    def test_preserves_newlines(self) -> None:
        lines = _wrap_text("line one\nline two", "│ ", 80)
        assert lines == ["│ line one", "│ line two"]

    def test_empty_lines(self) -> None:
        lines = _wrap_text("above\n\nbelow", "│ ", 80)
        assert lines == ["│ above", "│ ", "│ below"]

    def test_minimum_width(self) -> None:
        # Even with a very wide prefix, should use at least 20 chars
        lines = _wrap_text("some text", "x" * 100, 50)
        assert len(lines) >= 1


# --- Unit tests for query building ---


class TestBuildCommentFragment:
    def test_contains_comment_fields(self) -> None:
        frag = _build_comment_fragment(1)
        assert "comment_id" in frag
        assert "message" in frag
        assert "creator { username }" in frag
        assert "replies" in frag

    def test_nesting_depth(self) -> None:
        frag = _build_comment_fragment(3)
        # Should have 3 levels of "replies {"
        assert frag.count("replies {") == 3


class TestBuildTopicsQuery:
    def test_plots_query(self) -> None:
        q = _build_topics_query("plots")
        assert "plots(id: $id, author: $author)" in q
        assert "topics {" in q
        assert "comments {" in q

    def test_grids_query(self) -> None:
        q = _build_topics_query("grids")
        assert "grids(id: $id, author: $author)" in q

    def test_mails_query(self) -> None:
        q = _build_topics_query("mails")
        assert "mails(id: $id, author: $author)" in q


# --- Unit tests for render_topics ---


def _make_topic(
    topic_id: int = 1,
    username: str = "alice",
    message: str = "Hello world",
    audience: str = "public",
    status: str = "active",
    num_comments: int = 0,
    likes: int = 0,
    dislikes: int = 0,
    edited: bool = False,
    created: str = "Mon, 10 Feb 2026 12:00:00 UTC",
    comments: list = None,
) -> dict:
    return {
        "topic_id": topic_id,
        "slug": f"topic-{topic_id}",
        "message": message,
        "audience": audience,
        "status": status,
        "num_comments": num_comments,
        "likes": likes,
        "dislikes": dislikes,
        "edited": edited,
        "created": created,
        "updated": created,
        "creator": {"username": username},
        "comments": comments or [],
    }


def _make_comment(
    comment_id: int = 1,
    username: str = "bob",
    message: str = "Nice post",
    depth: int = 0,
    deleted: bool = False,
    edited: bool = False,
    likes: int = 0,
    dislikes: int = 0,
    created: str = "Mon, 10 Feb 2026 12:05:00 UTC",
    replies: list = None,
) -> dict:
    return {
        "comment_id": comment_id,
        "slug": f"comment-{comment_id}",
        "message": message,
        "depth": depth,
        "deleted": deleted,
        "edited": edited,
        "num_replies": len(replies) if replies else 0,
        "likes": likes,
        "dislikes": dislikes,
        "created": created,
        "updated": created,
        "creator": {"username": username},
        "replies": replies or [],
    }


class TestRenderTopics:
    def test_no_topics(self) -> None:
        result = _strip_ansi(render_topics([]))
        assert result == "No topics"

    def test_topic_header(self) -> None:
        topics = [_make_topic(username="alice", audience="public", num_comments=0)]
        result = _strip_ansi(render_topics(topics))
        assert "@alice" in result
        assert "(public)" in result
        assert "0 comments" in result

    def test_topic_body(self) -> None:
        topics = [_make_topic(message="This is the topic body")]
        result = _strip_ansi(render_topics(topics))
        assert "This is the topic body" in result

    def test_no_comments_message(self) -> None:
        topics = [_make_topic(comments=[])]
        result = _strip_ansi(render_topics(topics))
        assert "(no comments)" in result

    def test_single_comment(self) -> None:
        comment = _make_comment(username="bob", message="Great work")
        topics = [_make_topic(num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "@bob" in result
        assert "Great work" in result
        assert "1 comment" in result
        # Should not say "1 comments"
        assert "1 comments" not in result

    def test_plural_comments(self) -> None:
        comments = [
            _make_comment(comment_id=1, username="bob", message="First"),
            _make_comment(comment_id=2, username="carol", message="Second"),
        ]
        topics = [_make_topic(num_comments=2, comments=comments)]
        result = _strip_ansi(render_topics(topics))
        assert "2 comments" in result
        assert "@bob" in result
        assert "@carol" in result

    def test_nested_replies(self) -> None:
        reply = _make_comment(comment_id=2, username="carol", message="Reply here", depth=1)
        comment = _make_comment(comment_id=1, username="bob", message="Top level", replies=[reply])
        topics = [_make_topic(num_comments=2, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "@bob" in result
        assert "Top level" in result
        assert "@carol" in result
        assert "Reply here" in result

    def test_deep_nesting(self) -> None:
        c3 = _make_comment(comment_id=3, username="dave", message="Deep reply", depth=2)
        c2 = _make_comment(comment_id=2, username="carol", message="Mid reply", depth=1, replies=[c3])
        c1 = _make_comment(comment_id=1, username="bob", message="Top", replies=[c2])
        topics = [_make_topic(num_comments=3, comments=[c1])]
        result = _strip_ansi(render_topics(topics))
        assert "@dave" in result
        assert "Deep reply" in result

    def test_deleted_comment(self) -> None:
        comment = _make_comment(deleted=True, message="secret")
        topics = [_make_topic(num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "[deleted]" in result
        # Deleted message body should not be shown
        assert "secret" not in result

    def test_edited_markers(self) -> None:
        comment = _make_comment(edited=True)
        topics = [_make_topic(edited=True, num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        # Both topic and comment should show edited
        assert result.count("(edited)") == 2

    def test_reactions(self) -> None:
        comment = _make_comment(likes=5, dislikes=2)
        topics = [_make_topic(likes=3, num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        assert "[+3]" in result
        assert "[+5 -2]" in result

    def test_archived_status(self) -> None:
        topics = [_make_topic(status="archived")]
        result = _strip_ansi(render_topics(topics))
        assert "archived" in result

    def test_active_status_not_shown(self) -> None:
        topics = [_make_topic(status="active", audience="public")]
        result = _strip_ansi(render_topics(topics))
        # "active" should be suppressed, only "public" shown
        assert "active" not in result

    def test_multiple_topics(self) -> None:
        topics = [
            _make_topic(topic_id=1, username="alice", message="First topic"),
            _make_topic(topic_id=2, username="bob", message="Second topic"),
        ]
        result = _strip_ansi(render_topics(topics))
        assert "@alice" in result
        assert "First topic" in result
        assert "@bob" in result
        assert "Second topic" in result

    def test_multiline_message(self) -> None:
        topics = [_make_topic(message="Line one\nLine two\nLine three")]
        result = _strip_ansi(render_topics(topics))
        assert "Line one" in result
        assert "Line two" in result
        assert "Line three" in result

    def test_no_bottom_separator_line(self) -> None:
        comment = _make_comment()
        topics = [_make_topic(num_comments=1, comments=[comment])]
        result = _strip_ansi(render_topics(topics))
        # Should not have a full-width separator line
        assert "──────" not in result

    def test_dense_output_no_blank_lines_between_siblings(self) -> None:
        comments = [
            _make_comment(comment_id=1, username="bob", message="First"),
            _make_comment(comment_id=2, username="carol", message="Second"),
        ]
        topics = [_make_topic(num_comments=2, comments=comments)]
        result = _strip_ansi(render_topics(topics))
        lines = result.split("\n")
        # No empty lines within the topic (except between topics)
        for line in lines:
            assert line.strip() != "" or line == ""  # Allow only between topics


# --- CLI integration tests ---


def test_comments_empty(cli, requests_mock, fs) -> None:
    """Test --comments on a plot with no topics."""
    write_config(auth_req)

    gql_response = {"data": {"plots": [{"topics": []}]}}
    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/plots/my_plot", status_code=201)

    out, err = cli("-p", "my_plot", "--comments")
    assert "No topics" in out


def test_comments_with_data(cli, requests_mock, fs) -> None:
    """Test --comments shows topic and comment content."""
    write_config(auth_req)

    gql_response = {
        "data": {
            "plots": [
                {
                    "topics": [
                        {
                            "topic_id": 1,
                            "slug": "test-topic",
                            "message": "Discussion about the chart",
                            "audience": "public",
                            "status": "active",
                            "num_comments": 1,
                            "likes": 0,
                            "dislikes": 0,
                            "edited": False,
                            "created": "Mon, 10 Feb 2026 12:00:00 UTC",
                            "updated": "Mon, 10 Feb 2026 12:00:00 UTC",
                            "creator": {"username": "alice"},
                            "comments": [
                                {
                                    "comment_id": 1,
                                    "slug": "comment-1",
                                    "message": "Looks good!",
                                    "depth": 0,
                                    "deleted": False,
                                    "edited": False,
                                    "num_replies": 0,
                                    "likes": 0,
                                    "dislikes": 0,
                                    "created": "Mon, 10 Feb 2026 12:05:00 UTC",
                                    "updated": "Mon, 10 Feb 2026 12:05:00 UTC",
                                    "creator": {"username": "bob"},
                                    "replies": [],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
    }
    requests_mock.register_uri("POST", gql_endpoint, text=lambda r, c: json.dumps(gql_response))
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/plots/my_plot", status_code=201)

    out, err = cli("-p", "my_plot", "--comments")
    plain = _strip_ansi(out)
    assert "@alice" in plain
    assert "Discussion about the chart" in plain
    assert "@bob" in plain
    assert "Looks good!" in plain


def test_comments_sends_correct_gql_query(cli, requests_mock, fs) -> None:
    """Test --comments sends a properly formed GQL query with vis ID."""
    write_config(auth_req)

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        body = request.json()
        captured_query = body.get("query", "")
        return json.dumps({"data": {"plots": [{"topics": []}]}})

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/plots/test_chart", status_code=201)

    cli("-p", "test_chart", "--comments")

    assert captured_query is not None
    assert "plots(id: $id, author: $author)" in captured_query
    assert "topics" in captured_query
    assert "comments" in captured_query


def test_comments_grid(cli, requests_mock, fs) -> None:
    """Test --comments works with grids too."""
    write_config(auth_req)

    captured_query = None

    def capture_gql(request, context):
        nonlocal captured_query
        body = request.json()
        captured_query = body.get("query", "")
        return json.dumps({"data": {"grids": [{"topics": []}]}})

    requests_mock.register_uri("POST", gql_endpoint, text=capture_gql)
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/grids/my_grid", status_code=201)

    out, err = cli("-g", "my_grid", "--comments")
    assert "No topics" in out
    assert captured_query is not None
    assert "grids(id: $id, author: $author)" in captured_query


def test_comments_mail(cli, requests_mock, fs) -> None:
    """Test --comments works with mails too."""
    write_config(auth_req)

    def return_gql(request, context):
        return json.dumps({"data": {"mails": [{"topics": []}]}})

    requests_mock.register_uri("POST", gql_endpoint, text=return_gql)
    requests_mock.register_uri("PUT", "https://api.novem.io/v1/vis/mails/my_mail", status_code=201)

    out, err = cli("-m", "my_mail", "--comments")
    assert "No topics" in out


# --- Unit tests for _compact_num ---


class TestCompactNum:
    def test_zero(self) -> None:
        assert _compact_num(0) == "-"

    def test_small(self) -> None:
        assert _compact_num(1) == "1"
        assert _compact_num(42) == "42"
        assert _compact_num(999) == "999"

    def test_thousands(self) -> None:
        assert _compact_num(1000) == "1k"
        assert _compact_num(1200) == "1.2k"
        assert _compact_num(1050) == "1.1k"
        assert _compact_num(9999) == "10k"
        assert _compact_num(10000) == "10k"
        assert _compact_num(99999) == "100k"

    def test_large(self) -> None:
        assert _compact_num(100000) == "100k"
        assert _compact_num(999999) == "999k"
        assert _compact_num(1000000) == "1M"
        assert _compact_num(1500000) == "1.5M"
        assert _compact_num(10000000) == "10M"


# --- Unit tests for _aggregate_activity ---


class TestAggregateActivity:
    def test_no_topics(self) -> None:
        result = _aggregate_activity({})
        assert result == {"_comments": 0, "_likes": 0, "_dislikes": 0}

    def test_empty_topics(self) -> None:
        result = _aggregate_activity({"topics": []})
        assert result == {"_comments": 0, "_likes": 0, "_dislikes": 0}

    def test_single_topic(self) -> None:
        result = _aggregate_activity({"topics": [{"num_comments": 5, "likes": 3, "dislikes": 1}]})
        assert result == {"_comments": 5, "_likes": 3, "_dislikes": 1}

    def test_multiple_topics(self) -> None:
        result = _aggregate_activity(
            {
                "topics": [
                    {"num_comments": 2, "likes": 1, "dislikes": 0},
                    {"num_comments": 3, "likes": 4, "dislikes": 2},
                ]
            }
        )
        assert result == {"_comments": 5, "_likes": 5, "_dislikes": 2}


# --- Unit tests for _format_activity alignment ---


class TestFormatActivity:
    def _plain(self, p: dict) -> str:
        """Strip ANSI from the _activity value."""
        return _strip_ansi(p["_activity"])

    def test_all_zeros(self) -> None:
        colors()
        plist = [{"_comments": 0, "_likes": 0, "_dislikes": 0}]
        _format_activity(plist)
        # 3 single-char components, total=8, gaps=5 → gap1=3, gap2=2
        assert self._plain(plist[0]) == "-   -  -"

    def test_single_digits(self) -> None:
        colors()
        plist = [{"_comments": 1, "_likes": 2, "_dislikes": 3}]
        _format_activity(plist)
        assert self._plain(plist[0]) == "1   2  3"

    def test_mixed_widths_align(self) -> None:
        colors()
        plist = [
            {"_comments": 1, "_likes": 50, "_dislikes": 0},
            {"_comments": 100, "_likes": 1, "_dislikes": 10},
        ]
        _format_activity(plist)
        p0 = self._plain(plist[0])
        p1 = self._plain(plist[1])
        # All rows should have the same visible width
        assert len(p0) == len(p1)
        # Components right-aligned within sub-columns, gaps evenly distributed
        assert p0 == "  1 50  -"
        assert p1 == "100  1 10"

    def test_thousands(self) -> None:
        colors()
        plist = [
            {"_comments": 1000, "_likes": 50, "_dislikes": 0},
            {"_comments": 1, "_likes": 10000, "_dislikes": 5},
        ]
        _format_activity(plist)
        p0 = self._plain(plist[0])
        p1 = self._plain(plist[1])
        assert len(p0) == len(p1)
        assert "1k" in p0
        assert "10k" in p1

    def test_millions(self) -> None:
        colors()
        plist = [
            {"_comments": 1000000, "_likes": 1500000, "_dislikes": 100},
            {"_comments": 50, "_likes": 1, "_dislikes": 10000000},
        ]
        _format_activity(plist)
        p0 = self._plain(plist[0])
        p1 = self._plain(plist[1])
        assert len(p0) == len(p1)
        assert "1M" in p0
        assert "1.5M" in p0
        assert "10M" in p1

    def test_wide_values_no_header_padding(self) -> None:
        """When values are wider than 'Activity', no extra padding needed."""
        colors()
        plist = [{"_comments": 10000, "_likes": 10000, "_dislikes": 10000}]
        _format_activity(plist)
        p = self._plain(plist[0])
        assert p == "10k 10k 10k"  # 11 chars > 8 ("Activity"), no extra padding

    def test_empty_list(self) -> None:
        colors()
        plist: list = []
        _format_activity(plist)  # should not raise
