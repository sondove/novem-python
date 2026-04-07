from inspect import signature
from typing import Optional

from .mail_sections import (
    AuthorSection,
    CalloutSection,
    CodeSection,
    MarkdownSection,
    NovemEmailSection,
    NovemEmailSectionApi,
    ParagraphSection,
    PreviewSection,
    VisSection,
)

# Re-export shared sections for convenience
__all__ = [
    "NovemDocSection",
    "PageSection",
    "HtmlSection",
    "FrontmatterSection",
    "VisSection",
    "CalloutSection",
    "ParagraphSection",
    "AuthorSection",
    "PreviewSection",
    "MarkdownSection",
    "CodeSection",
]

# Alias for doc context
NovemDocSection = NovemEmailSection


class PageSection(NovemEmailSectionApi):
    def __init__(
        self,
        /,
        orient: Optional[str] = None,
        cols: Optional[str] = None,
        type: Optional[str] = None,
        footer: Optional[str] = None,
        pnum: Optional[str] = None,
        overflow: Optional[str] = None,
        ref: Optional[str] = None,
        **kwargs: str,
    ) -> None:
        """Add a page break to your document.

        :param orient: Page orientation — portrait or landscape.
        :type orient: str, optional
        :param cols: Number of columns (1, 2, or 3).
        :type cols: str, optional
        :param type: Page type — fp, index, centered, or blank.
        :type type: str, optional
        :param footer: Footer text or true/false.
        :type footer: str, optional
        :param pnum: Page number override.
        :type pnum: str, optional
        :param overflow: Overflow behavior (auto).
        :type overflow: str, optional
        :param ref: Embed another vis as a full page (FQNP or shortname).
        :type ref: str, optional
        """
        self._type = "page"
        self._subtype = "single"

        locs = locals()

        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

    def get_markdown(self) -> str:
        """Page sections are always single-statement (no closing tag)."""

        ot = f"{{{{ {self._type}"

        plist = self._params + self._kwparams + self._cparams

        for p in plist:
            if not len(p):
                continue
            ot = f"{ot}\n  {p}"

        if len(plist):
            ot = f"{ot}\n"
        else:
            ot = f"{ot} "

        ot = f"{ot}}}}}"

        return ot


class HtmlSection(NovemEmailSectionApi):
    def __init__(
        self,
        html: str,
        /,
        **kwargs: str,
    ) -> None:
        """Add raw HTML to your document.

        :param html: Raw HTML content.
        :type html: str
        """
        self._type = "html"
        self._subtype = "double"

        locs = locals()

        super().__init__(locs, signature(self.__class__.__init__).parameters, **kwargs)

        self._body = html


class FrontmatterSection(NovemEmailSection):
    def __init__(self, **kwargs: str) -> None:
        """Add YAML frontmatter to the beginning of your document.

        :param kwargs: Key-value pairs for frontmatter fields
            (title, author, date, theme, etc.)
        """
        super().__init__()
        self._fields = kwargs

    def get_markdown(self) -> str:
        if not self._fields:
            return ""

        lines = ["---"]
        for k, v in self._fields.items():
            lines.append(f"{k}: {v}")
        lines.append("---")

        return "\n".join(lines)
