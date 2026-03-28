#!/usr/bin/env python3
"""Parse SFS XML from rinfo.gov.se into structured data and Markdown.

This module handles the conversion between the authoritative SFS XML format
and the Markdown format used in the Lagläget repository.
"""

import re
from xml.etree import ElementTree as ET

import yaml


class SFSParser:
    """Parse SFS documents from various formats into structured data."""

    # Common XML namespaces used by rinfo.gov.se
    NAMESPACES = {
        "rinfo": "http://rinfo.lagrummet.se/taxo/2007/09/rinfo/pub#",
        "dct": "http://purl.org/dc/terms/",
        "rpubl": "http://rinfo.lagrummet.se/ns/2008/11/rinfo/publ#",
    }

    def parse(self, xml_content: str) -> dict:
        """Parse SFS XML into a structured dictionary.

        Args:
            xml_content: Raw XML string from rinfo.gov.se

        Returns:
            Dictionary with parsed law metadata and structure.
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML: {e}") from e

        result = {
            "sfs": self._extract_sfs_number(root),
            "titel": self._extract_title(root),
            "kortnamn": self._extract_short_name(root),
            "departement": self._extract_department(root),
            "typ": self._extract_type(root),
            "ikraftträdande": self._extract_date(root, "ikraftträdandedatum"),
            "upphävd": self._extract_date(root, "upphävandedatum"),
            "eu_direktiv": self._extract_eu_directives(root),
            "kapitel": self._extract_chapters(root),
        }
        return result

    def _extract_sfs_number(self, root: ET.Element) -> str:
        """Extract the SFS number (e.g. '1962:700')."""
        for ns_prefix in ["rpubl", "dct"]:
            ns = self.NAMESPACES.get(ns_prefix, "")
            for elem in root.iter(f"{{{ns}}}identifier" if ns else "identifier"):
                text = elem.text or ""
                match = re.search(r"(\d{4}:\d+)", text)
                if match:
                    return match.group(1)

        # Fallback: search all text content
        xml_str = ET.tostring(root, encoding="unicode")
        match = re.search(r"SFS\s*(\d{4}:\d+)", xml_str)
        if match:
            return match.group(1)

        raise ValueError("Could not extract SFS number from document")

    def _extract_title(self, root: ET.Element) -> str:
        """Extract the full title."""
        for tag in ["title", "titel", "rubrik"]:
            for elem in root.iter(tag):
                if elem.text:
                    return elem.text.strip()
        return "Okänd titel"

    def _extract_short_name(self, root: ET.Element) -> str | None:
        """Extract the common abbreviation (e.g. 'BrB')."""
        for elem in root.iter("kortnamn"):
            if elem.text:
                return elem.text.strip()
        return None

    def _extract_department(self, root: ET.Element) -> str:
        """Extract the responsible department."""
        for tag in ["departement", "publisher"]:
            for elem in root.iter(tag):
                if elem.text:
                    return elem.text.strip()
        return "Okänt departement"

    def _extract_type(self, root: ET.Element) -> str:
        """Determine if this is a lag, förordning, or grundlag."""
        xml_str = ET.tostring(root, encoding="unicode").lower()
        if "grundlag" in xml_str:
            return "grundlag"
        elif "förordning" in xml_str:
            return "förordning"
        return "lag"

    def _extract_date(self, root: ET.Element, field: str) -> str | None:
        """Extract a date field."""
        for elem in root.iter(field):
            if elem.text:
                return elem.text.strip()[:10]  # ISO date portion
        return None

    def _extract_eu_directives(self, root: ET.Element) -> list[str]:
        """Extract referenced EU directive IDs."""
        directives = []
        xml_str = ET.tostring(root, encoding="unicode")
        for match in re.finditer(r"(\d{4}/\d+/E[GU]|\d{4}/\d+)", xml_str):
            directive_id = match.group(1)
            if directive_id not in directives:
                directives.append(directive_id)
        return directives

    def _extract_chapters(self, root: ET.Element) -> list[dict]:
        """Extract chapter and paragraph structure."""
        chapters = []
        for elem in root.iter("kapitel"):
            chapter = {
                "nummer": elem.get("nummer", ""),
                "rubrik": elem.get("rubrik", ""),
                "paragrafer": [],
            }
            for para in elem.iter("paragraf"):
                chapter["paragrafer"].append(
                    {
                        "nummer": para.get("nummer", ""),
                        "text": (para.text or "").strip(),
                    }
                )
            chapters.append(chapter)
        return chapters

    def to_markdown(self, parsed: dict) -> str:
        """Convert parsed SFS data to Markdown with YAML frontmatter.

        Args:
            parsed: Dictionary from self.parse()

        Returns:
            Complete Markdown string with frontmatter.
        """
        # Build frontmatter
        frontmatter = {
            "sfs": parsed["sfs"],
            "titel": parsed["titel"],
            "departement": parsed["departement"],
            "typ": parsed["typ"],
            "ikraftträdande": parsed.get("ikraftträdande", "okänd"),
            "upphävd": parsed.get("upphävd"),
            "eu_direktiv": parsed.get("eu_direktiv", []),
            "relaterade_lagar": [],
            "riksdagen_dok_id": None,
            "ändringshistorik": [],
        }
        if parsed.get("kortnamn"):
            frontmatter["kortnamn"] = parsed["kortnamn"]

        fm_yaml = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        # Build body
        lines = [f"---\n{fm_yaml}---\n"]
        lines.append(f"# {parsed['titel']}\n")

        chapters = parsed.get("kapitel", [])
        if chapters:
            for chapter in chapters:
                nummer = chapter.get("nummer", "")
                rubrik = chapter.get("rubrik", "")
                lines.append(f"\n## {nummer} kap. {rubrik}\n")

                for para in chapter.get("paragrafer", []):
                    p_nummer = para.get("nummer", "")
                    p_text = para.get("text", "")
                    lines.append(f"\n### {p_nummer} §\n")
                    lines.append(f"{p_text}\n")

        return "\n".join(lines)

    def parse_markdown(self, markdown: str) -> dict:
        """Parse a Lagläget Markdown file back into structured data.

        Args:
            markdown: Complete Markdown string with YAML frontmatter.

        Returns:
            Dictionary with frontmatter fields and body text.
        """
        if not markdown.startswith("---"):
            raise ValueError("Markdown file must start with YAML frontmatter (---)")

        parts = markdown.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Could not find closing --- for frontmatter")

        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip()

        return {**frontmatter, "body": body}
