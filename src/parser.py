"""Manual POM XML and local test graph parsing."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .errors import PomParseError, RepositoryError

PROPERTY_PATTERN = re.compile(r"\$\{([^}]+)\}")
IGNORED_SCOPES = {"test", "provided", "system"}
MAVEN_NAMESPACE = "{http://maven.apache.org/POM/4.0.0}"


def _tag(name: str) -> str:
    """Return a Maven POM tag with its optional namespace."""
    return f"{MAVEN_NAMESPACE}{name}"


def parse_pom(xml_text: str) -> list[str]:
    """Extract direct dependency coordinates from POM XML text."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise PomParseError(f"Malformed pom.xml: {exc}") from exc

    properties = {}
    properties_node = root.find(_tag("properties"))
    if properties_node is not None:
        for child in list(properties_node):
            properties[child.tag.split("}")[-1]] = (child.text or "").strip()

    dependencies = root.find(_tag("dependencies"))
    if dependencies is None:
        dependencies = root.find("dependencies")
    if dependencies is None:
        return []

    result = []
    for dependency in dependencies.findall(_tag("dependency")):
        if not dependency.findall("*"):
            continue
        group = _child_text(dependency, "groupId")
        artifact = _child_text(dependency, "artifactId")
        version = _child_text(dependency, "version")
        scope = _child_text(dependency, "scope") or "compile"
        optional = _child_text(dependency, "optional").lower() == "true"
        if not group or not artifact or optional:
            continue
        if scope in IGNORED_SCOPES:
            continue
        version = _resolve_properties(version, properties)
        if version:
            result.append(f"{group}:{artifact}:{version}")
    return result


def _child_text(parent: ET.Element, name: str) -> str:
    """Read and trim the text of a direct child element."""
    child = parent.find(_tag(name))
    if child is None:
        child = parent.find(name)
    return (child.text or "").strip() if child is not None else ""


def _resolve_properties(value: str, properties: dict[str, str]) -> str:
    """Resolve simple Maven property references without recursion."""
    for _ in range(len(properties) + 1):
        match = PROPERTY_PATTERN.search(value)
        if match is None:
            return value
        replacement = properties.get(match.group(1))
        if replacement is None:
            return ""
        value = value[:match.start()] + replacement + value[match.end():]
    return ""


def parse_test_graph(path: str) -> dict[str, list[str]]:
    """Parse lines formatted as 'PACKAGE: DEP1, DEP2'."""
    file_path = Path(path)
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RepositoryError(f"Cannot read test graph: {exc}") from exc

    graph = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise RepositoryError(
                f"Invalid test graph line {line_number}: missing ':'."
            )
        package, dependency_text = line.split(":", maxsplit=1)
        package = package.strip()
        if not package or not package.isalpha() or not package.isupper():
            raise RepositoryError(
                f"Invalid package name on line {line_number}: {package!r}"
            )
        if package in graph:
            raise RepositoryError(
                f"Duplicate package on line {line_number}: {package}"
            )
        dependencies = [
            item.strip() for item in dependency_text.split(",")
            if item.strip()
        ]
        if any(not item.isalpha() or not item.isupper()
               for item in dependencies):
            raise RepositoryError(
                f"Invalid dependency on line {line_number}."
            )
        graph[package] = dependencies
    return graph
