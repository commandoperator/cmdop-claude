"""Scan subpackage."""
from cmdop_claude.sidecar.scan.scanner import full_scan, scan_doc_files, scan_dependencies, scan_git_log, scan_top_dirs
from cmdop_claude.sidecar.scan.toon import to_toon, paths_to_tree, to_grouped_prefix_blocks
from cmdop_claude.sidecar.scan.tree_summarizer import TreeSummarizer
from cmdop_claude.sidecar.scan._sidecar_section import inject_sidecar_workflow

__all__ = [
    "full_scan",
    "scan_doc_files",
    "scan_dependencies",
    "scan_git_log",
    "scan_top_dirs",
    "to_toon",
    "paths_to_tree",
    "to_grouped_prefix_blocks",
    "TreeSummarizer",
    "inject_sidecar_workflow",
]
