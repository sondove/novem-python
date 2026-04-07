import configparser
import os

from novem import Doc, Plot
from novem.vis.doc_sections import (
    CalloutSection,
    FrontmatterSection,
    HtmlSection,
    MarkdownSection,
    PageSection,
    ParagraphSection,
    VisSection,
)


def setup_doc_mock(requests_mock, conf):
    """Setup mocked API endpoints for a doc."""
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"

    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    doc_id = conf["doc_id"]

    requests_mock.register_uri(
        "put",
        f"{api_root}vis/docs/{doc_id}",
        text="",
    )

    for method, path, value in conf.get("reqs", []):
        requests_mock.register_uri(
            method,
            f"{api_root}vis/docs/{doc_id}{path}",
            text=value,
        )

    return Doc(
        doc_id,
        config_path=config_file,
        create=True,
    )


# --- Property tests ---


def test_doc_attrib_name(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["get", "/name", "Test Document"],
            ["post", "/name", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)
    d.name = "New Name"
    assert d.name == "Test Document"


def test_doc_attrib_description(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["get", "/description", "A test description"],
            ["post", "/description", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)
    d.description = "Updated description"
    assert d.description == "A test description"


def test_doc_attrib_theme(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["get", "/config/theme", "novem"],
            ["post", "/config/theme", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)
    d.theme = "novem-dark"
    assert d.theme == "novem"


def test_doc_attrib_type(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["get", "/config/type", "doc"],
            ["post", "/config/type", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)
    d.type = "pptx"
    assert d.type == "doc"


def test_doc_attrib_title(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["get", "/config/title", "Document Title"],
            ["post", "/config/title", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)
    d.title = "New Title"
    assert d.title == "Document Title"


def test_doc_attrib_content(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["get", "/content", "# Hello World"],
            ["post", "/content", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)
    d.content = "# Updated"
    assert d.content == "# Hello World"


# --- Section tests ---


def test_doc_page_section():
    section = PageSection(orient="landscape", cols="2")
    md = section.get_markdown()
    assert "{{ page" in md
    assert "orient: landscape" in md
    assert "cols: 2" in md
    assert "{{ /page" not in md  # single-statement, no closing tag


def test_doc_page_section_empty():
    section = PageSection()
    md = section.get_markdown()
    assert md == "{{ page }}"


def test_doc_page_section_with_ref():
    section = PageSection(ref="/u/demo/d/other-doc", orient="landscape")
    md = section.get_markdown()
    assert "ref: /u/demo/d/other-doc" in md
    assert "orient: landscape" in md


def test_doc_html_section():
    section = HtmlSection("<div>Raw HTML</div>")
    md = section.get_markdown()
    assert "{{ html" in md
    assert "<div>Raw HTML</div>" in md
    assert "{{ /html }}" in md


def test_doc_frontmatter_section():
    section = FrontmatterSection(
        title="Test Document",
        author="Test Author",
        date="January 2025",
    )
    md = section.get_markdown()
    assert md.startswith("---")
    assert md.endswith("---")
    assert "title: Test Document" in md
    assert "author: Test Author" in md
    assert "date: January 2025" in md


def test_doc_frontmatter_empty():
    section = FrontmatterSection()
    md = section.get_markdown()
    assert md == ""


def test_doc_paragraph_section():
    section = ParagraphSection("**Bold text**", font_size="l", font_style="b")
    md = section.get_markdown()
    assert "{{ paragraph" in md
    assert "font size: l" in md
    assert "font style: b" in md
    assert "**Bold text**" in md
    assert "{{ /paragraph }}" in md


def test_doc_callout_section():
    section = CalloutSection("Warning message", type="warn")
    md = section.get_markdown()
    assert "{{ callout" in md
    assert "type: warn" in md
    assert "Warning message" in md
    assert "{{ /callout }}" in md


def test_doc_vis_section(requests_mock):
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    requests_mock.register_uri("put", f"{api_root}vis/plots/test_plot", text="")
    requests_mock.register_uri("get", f"{api_root}vis/plots/test_plot/shortname", text="ABCDEF")

    plt = Plot("test_plot", config_path=config_file, create=True)
    section = VisSection(plt, width="80%", align="center")
    md = section.get_markdown()
    assert "{{ vis" in md
    assert "ref: ABCDEF" in md
    assert "width: 80%" in md


# --- Produce content ---


def test_doc_produce_content(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["post", "/content", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)

    d.add_section(FrontmatterSection(title="Test", author="Author"))
    d.add_section(MarkdownSection("# Introduction\n\nSome text."))
    d.add_section(PageSection(orient="landscape", cols="2"))
    d.add_section(MarkdownSection("## Charts"))
    d.add_section(CalloutSection("Important note", type="info"))

    content = d._produce_content()
    assert content.startswith("---")
    assert "title: Test" in content
    assert "# Introduction" in content
    assert "{{ page" in content
    assert "orient: landscape" in content
    assert "## Charts" in content
    assert "{{ callout" in content


# --- Callable interface ---


def test_doc_callable(requests_mock):
    conf = {
        "doc_id": "test_doc",
        "reqs": [
            ["post", "/content", ""],
        ],
    }
    d = setup_doc_mock(requests_mock, conf)
    result = d("# Hello World")
    assert result == "# Hello World"  # returns content, matching mail pattern


# --- Kwargs ---


def test_doc_kwargs(requests_mock):
    base = os.path.dirname(os.path.abspath(__file__))
    config_file = f"{base}/test.conf"
    config = configparser.ConfigParser()
    config.read(config_file)
    api_root = config["general"]["api_root"]

    requests_mock.register_uri("put", f"{api_root}vis/docs/test_doc", text="")
    requests_mock.register_uri("post", f"{api_root}vis/docs/test_doc/name", text="")
    requests_mock.register_uri("post", f"{api_root}vis/docs/test_doc/config/theme", text="")
    requests_mock.register_uri("post", f"{api_root}vis/docs/test_doc/content", text="")

    Doc(
        "test_doc",
        config_path=config_file,
        create=True,
        name="My Document",
        theme="novem-dark",
        content="# Hello",
    )
    # Should not crash — kwargs processed in order
