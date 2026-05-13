"""테스트 전용 AST 조회 헬퍼.

여러 테스트 파일이 동일 패턴(파일 → ast.Module → ClassDef → FunctionDef)을
독립적으로 정의하던 것을 통합한다. `read_module` 은 source 와 module 을 함께
반환해 `ast.get_source_segment` 가 필요한 호출자도 한 번에 처리된다.
"""
from __future__ import annotations

import ast
from pathlib import Path


def read_module(path: str) -> tuple[str, ast.Module]:
    """파일을 읽어 (원본 텍스트, ast.Module) 튜플을 반환한다."""
    source = Path(path).read_text(encoding="utf-8")
    return source, ast.parse(source)


def parse_module(path: str) -> ast.Module:
    """source 가 필요 없는 호출자를 위한 간편 변형."""
    return read_module(path)[1]


def find_class(module: ast.Module, name: str) -> ast.ClassDef:
    return next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == name)


def find_function(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(n for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name == name)


def find_module_function(module: ast.Module, name: str) -> ast.FunctionDef:
    return next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)


def function_source(source: str, node: ast.FunctionDef) -> str:
    """node 의 원문을 안전하게 추출. 비어 있으면 빈 문자열."""
    return ast.get_source_segment(source, node) or ""
