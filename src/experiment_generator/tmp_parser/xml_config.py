from lxml import etree
from pathlib import Path


def read_xml(path: Path) -> etree._ElementTree:
    """
    Parses an XML file and returns its ElementTree.
    It preserves indentation and formatting.
    """

    parser = etree.XMLParser(
        remove_blank_text=True,
        remove_comments=False,
        strip_cdata=False,
        resolve_entities=False,
    )

    return etree.parse(str(path), parser)


def write_xml(tree: etree._ElementTree, path: Path) -> None:
    """
    Writes an ElementTree to an XML file, preserving formatting.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tree.write(
        str(tmp),
        pretty_print=True,
        xml_declaration=True,
        encoding="utf-8",
    )
    tmp.replace(path)
