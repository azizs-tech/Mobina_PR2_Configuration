"""Iterative graph construction, traversal, trees, and topological sort."""

from collections import deque

from .errors import GraphError


def build_graph(
    root: str,
    dependency_loader,
    max_depth: int,
    filter_substring: str = "",
) -> dict[str, list[str]]:
    """Build a bounded dependency graph using breadth-first search."""
    graph = {root: []}
    queue = deque([(root, 0)])
    expanded = set()
    while queue:
        package, depth = queue.popleft()
        if package in expanded or depth >= max_depth:
            continue
        expanded.add(package)
        dependencies = dependency_loader(package)
        accepted = [
            dep for dep in dependencies
            if not filter_substring or filter_substring not in dep
        ]
        graph.setdefault(package, [])
        graph[package] = accepted
        for dependency in accepted:
            graph.setdefault(dependency, [])
            if dependency not in expanded:
                queue.append((dependency, depth + 1))
    return graph


def filter_graph(
    graph: dict[str, list[str]],
    substring: str,
) -> dict[str, list[str]]:
    """Remove nodes and edges whose package name contains a substring."""
    if not substring:
        return {node: list(edges) for node, edges in graph.items()}
    filtered = {}
    for node, edges in graph.items():
        if substring in node:
            continue
        filtered[node] = [
            edge for edge in edges if substring not in edge
        ]
    return filtered


def ascii_tree(graph: dict[str, list[str]], root: str) -> str:
    """Render a graph as an ASCII tree while marking repeated nodes."""
    if root not in graph:
        raise GraphError(f"Root package is not in graph: {root}")
    lines = [root]
    seen = {root}
    stack = [(root, "", set())]
    while stack:
        node, prefix, ancestors = stack.pop()
        children = graph.get(node, [])
        for index in range(len(children) - 1, -1, -1):
            child = children[index]
            last = index == len(children) - 1
            branch = "`-- " if last else "|-- "
            marker = " [already shown]" if child in seen else ""
            lines.append(f"{prefix}{branch}{child}{marker}")
            if child not in seen:
                seen.add(child)
                next_prefix = prefix + ("    " if last else "|   ")
                stack.append((child, next_prefix, ancestors | {node}))
    return "\n".join(lines)


def topological_sort(graph: dict[str, list[str]]) -> list[str]:
    """Return dependency-first order, raising an error for cycles."""
    nodes = set(graph)
    for dependencies in graph.values():
        nodes.update(dependencies)
    indegree = {node: 0 for node in nodes}
    dependents = {node: [] for node in nodes}
    for package, dependencies in graph.items():
        for dependency in dependencies:
            dependents[dependency].append(package)
            indegree[package] += 1
    ready = deque(sorted(node for node, degree in indegree.items()
                         if degree == 0))
    result = []
    while ready:
        node = ready.popleft()
        result.append(node)
        for dependent in dependents[node]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if len(result) != len(nodes):
        raise GraphError("Dependency cycle detected; load order is undefined.")
    return result
