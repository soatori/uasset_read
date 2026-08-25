"""
C++ JSON IR formatter module — CppProperty, CppHeaderMeta, CppClassIR, CppStatement data models.

Per D-06: JSON IR structure contains header_meta, properties, methods, constructor sections.
Only header_meta and properties are populated; methods and constructor are left empty.

Exports:
    CppProperty: single C++ UPROPERTY declaration data model
    CppHeaderMeta: header file metadata model
    CppClassIR: complete C++ class skeleton IR data model
    format_cpp_class_json: JSON IR formatting function
    kismet_to_cpp_body: Kismet expressions → structured C++ statement list
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import logging

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.translator import KismetTranslator

logger = logging.getLogger(__name__)


# ============================================================================
# C++ Property Data Model (Per D-06)
# ============================================================================

@dataclass
class CppProperty:
    """Single C++ UPROPERTY declaration.

    Represents a C++ property declaration for a Blueprint variable or component.

    Attributes:
        cpp_type: C++ type name (e.g. "USceneComponent*", "FVector", "float")
        name: property name (e.g. "DefaultSceneRoot", "MoveSpeed")
        uproperty_marks: UPROPERTY specifiers list (e.g. ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"])
        category: property category ("component" or "variable")
        default_value: default value (None for components, 100.0 for float variables)
        cpp_comment: optional comment (original UE type reference)
    """
    cpp_type: str
    name: str
    uproperty_marks: List[str]
    category: str  # "component" or "variable"
    default_value: Any = None
    cpp_comment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict (D-06 format).

        Returns:
            Dict containing all fields; default_value is kept as-is (None -> JSON null)
        """
        result = {
            "cpp_type": self.cpp_type,
            "name": self.name,
            "uproperty_marks": self.uproperty_marks,
            "category": self.category,
            "default_value": self.default_value,
        }
        if self.cpp_comment:
            result["cpp_comment"] = self.cpp_comment
        return result


# ============================================================================
# C++ Header Metadata Model (Per D-05, D-06)
# ============================================================================

@dataclass
class CppHeaderMeta:
    """Header file metadata.

    Per D-05: full UE header file template structure.

    Attributes:
        pragma_once: whether to include #pragma once (default True)
        includes: list of included header files (e.g. '"Engine/GameFramework/Character.h"')
        forward_declarations: forward declaration list
        generated_include: .generated.h include path (must be the last include)
    """
    pragma_once: bool = True
    includes: List[str] = field(default_factory=list)
    forward_declarations: List[str] = field(default_factory=list)
    generated_include: str = ""

    @classmethod
    def build_from_parent(cls, parent_class: str, class_name: str) -> "CppHeaderMeta":
        """Build header metadata from parent class.

        Per D-05: set generated_include to '{class_name}.generated.h'.
        Add corresponding header file includes based on parent class type.

        Args:
            parent_class: parent class C++ name (e.g. "ACharacter", "UActorComponent")
            class_name: current class name (used to generate .generated.h path)

        Returns:
            Configured CppHeaderMeta instance
        """
        # T-056-04: sanitize class name - allow only alphanumeric and underscores
        if class_name:
            import re
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', class_name):
                logger.warning(f"Invalid class name format: '{class_name}', sanitizing")
                # Remove invalid characters
                class_name = re.sub(r'[^A-Za-z0-9_]', '_', class_name)

        meta = cls(
            pragma_once=True,
            includes=[],
            forward_declarations=[],
            generated_include=f'"{class_name}.generated.h"' if class_name else ""
        )

        # Infer header file path from parent class prefix
        if parent_class:
            # Extract class name part (remove prefix)
            base_name = parent_class
            if parent_class.startswith(('A', 'U', 'F', 'E', 'I')):
                base_name = parent_class[1:]

            # Actor classes use GameFramework path
            if parent_class.startswith('A'):
                meta.includes.append(f'"Engine/GameFramework/{base_name}.h"')
            # Component classes use Components path
            elif parent_class.startswith('U') and base_name.endswith('Component'):
                meta.includes.append(f'"Components/{base_name}.h"')
            # Other UObject-derived classes
            elif parent_class.startswith('U'):
                meta.includes.append(f'"Engine/{base_name}.h"')
            # Structs
            elif parent_class.startswith('F'):
                # Core structs are in CoreUObject
                if base_name in ('Vector', 'Rotator', 'Transform', 'Vector2D',
                                  'LinearColor', 'Color', 'Guid', 'Quat', 'Plane', 'Box'):
                    meta.includes.append('"CoreUObject.h"')
                else:
                    meta.includes.append(f'"Engine/{base_name}.h"')

        return meta

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict (D-06 format)."""
        return {
            "pragma_once": self.pragma_once,
            "includes": self.includes,
            "forward_declarations": self.forward_declarations,
            "generated_include": self.generated_include,
        }


@dataclass
class CppCallParameter:
    """Single parameter in a function/call.

    Attributes:
        name: sanitized C++ identifier (e.g. "LeftRight")
        cpp_type: C++ type (with direction modifier, e.g. "const FString&", "double")
        direction: "input" | "output" | "return"
    """
    name: str
    cpp_type: str
    direction: str  # "input" | "output" | "return"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cpp_type": self.cpp_type,
            "direction": self.direction,
        }


@dataclass
class CppMethodIR:
    """Blueprint function -> C++ method declaration (D-57-02).

    Attributes:
        cpp_name: C++ function name (sanitized, e.g. "PrimaryThumbstick")
        return_type: C++ return type (default "void")
        parameters: Argument list
        ufunction_specifiers: UFUNCTION macro specifiers (e.g. ["BlueprintCallable"])
        is_override: True indicates K2Node_Event bOverrideFunction
        is_const: const method modifier (default False)
        is_static: static method modifier
        is_virtual: virtual method modifier
        is_pure: pure function (no side effects)
        is_event: event function
        is_native: native function
        access_modifier: access modifier ("public", "protected", "private")
        source_node_type: "K2Node_FunctionEntry" | "K2Node_Event" | ""
        body: function body statements (structured IR)
        body_text: Kismet decompiled function body text (raw C++ pseudocode)
    """
    cpp_name: str
    return_type: str
    parameters: List[CppCallParameter]
    ufunction_specifiers: List[str]
    is_override: bool
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure: bool = False
    is_event: bool = False
    is_native: bool = False
    access_modifier: str = "protected"  # default protected
    source_node_type: str = ""
    class_name: str = ""  # owning class name (for ClassName::Method prefix in .cpp implementation)
    body: List["CppStatement"] = field(default_factory=list)  # function body statements
    body_text: Optional[str] = None  # Kismet decompiled function body text (D-66-03)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "cpp_name": self.cpp_name,
            "return_type": self.return_type,
            "parameters": [p.to_dict() for p in self.parameters],
            "ufunction_specifiers": self.ufunction_specifiers,
            "is_override": self.is_override,
            "is_const": self.is_const,
            "is_static": self.is_static,
            "is_virtual": self.is_virtual,
            "is_pure": self.is_pure,
            "is_event": self.is_event,
            "is_native": self.is_native,
            "access_modifier": self.access_modifier,
            "source_node_type": self.source_node_type,
            "body": [s.to_dict() for s in self.body],
        }
        if self.class_name:
            result["class_name"] = self.class_name
        if self.body_text is not None:
            result["body_text"] = self.body_text
        return result


@dataclass
class CppCallStatement:
    """K2Node_CallFunction -> C++ call statement reference (D-57-02).

    Attributes:
        method_name: called method name
        target: call target ("this" or variable name)
        target_type: "this" | "pointer" (controls -> access operator)
        args: argument name list (sanitized identifiers)
        is_self_context: from FMemberReference.b_self_context
    """
    method_name: str
    target: str
    target_type: str = "pointer"
    args: List[str] = field(default_factory=list)
    is_self_context: bool = True


@dataclass
class CppStatement:
    """C++ statement base class.

    All concrete statement types inherit from this class, representing a single C++ statement in a function body.
    """
    statement_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"statement_type": self.statement_type}


@dataclass
class CppCallStmt(CppStatement):
    """Function call statement.

    Attributes:
        target: call target object ("Super", "this", or variable name)
        method_name: method name
        args: argument list (strings)
        is_pure: whether this is a pure function call
    """
    target: str = ""
    method_name: str = ""
    args: List[str] = field(default_factory=list)
    is_pure: bool = False
    statement_type: str = "call"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "target": self.target,
            "method_name": self.method_name,
            "args": self.args,
            "is_pure": self.is_pure,
        }


@dataclass
class CppAssignmentStmt(CppStatement):
    """Assignment statement: lhs = rhs;

    Attributes:
        lhs: left-hand side variable name
        rhs: right-hand side expression
        cpp_type: C++ type
    """
    lhs: str = ""
    rhs: str = ""
    cpp_type: str = ""
    statement_type: str = "assignment"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "lhs": self.lhs,
            "rhs": self.rhs,
            "cpp_type": self.cpp_type,
        }


@dataclass
class CppIfStmt(CppStatement):
    """Conditional statement: if (condition) { then_body } [else { else_body }]

    Attributes:
        condition: condition expression
        then_body: then-branch statement list
        else_body: else-branch statement list (may be empty)
    """
    condition: str = ""
    then_body: List["CppStatement"] = field(default_factory=list)
    else_body: List["CppStatement"] = field(default_factory=list)
    statement_type: str = "if"

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "statement_type": self.statement_type,
            "condition": self.condition,
            "then_body": [s.to_dict() for s in self.then_body],
        }
        if self.else_body:
            result["else_body"] = [s.to_dict() for s in self.else_body]
        return result


@dataclass
class CppInlineExprStmt(CppStatement):
    """Inline expression statement (not standalone, embedded in other statement parameters).

    Attributes:
        expression: inline expression text
    """
    expression: str = ""
    statement_type: str = "inline_expr"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "expression": self.expression,
        }


@dataclass
class CppReturnStmt(CppStatement):
    """Return statement.

    Attributes:
        value: return value expression (empty string for void return)
    """
    value: str = ""
    statement_type: str = "return"

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"statement_type": self.statement_type}
        if self.value:
            result["value"] = self.value
        return result


@dataclass
class CppWhileStmt(CppStatement):
    """While loop statement.

    Attributes:
        condition: loop condition expression
    """
    condition: str = ""
    statement_type: str = "while"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "condition": self.condition,
        }


@dataclass
class CppForStmt(CppStatement):
    """For loop statement: for (init; condition; increment) { body }

    Attributes:
        init: initialization expression
        condition: loop condition
        increment: increment expression
        body: loop body statement list
    """
    init: str = ""
    condition: str = ""
    increment: str = ""
    body: List["CppStatement"] = field(default_factory=list)
    statement_type: str = "for"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "init": self.init,
            "condition": self.condition,
            "increment": self.increment,
            "body": [s.to_dict() for s in self.body],
        }


@dataclass
class CppForEachStmt(CppStatement):
    """Range-based for loop: for (auto& elem : container) { body }

    Attributes:
        element: loop variable name
        element_type: element type (default "auto&")
        container: container expression
        body: loop body statement list
    """
    element: str = ""
    element_type: str = "auto&"
    container: str = ""
    body: List["CppStatement"] = field(default_factory=list)
    statement_type: str = "for_each"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "element": self.element,
            "element_type": self.element_type,
            "container": self.container,
            "body": [s.to_dict() for s in self.body],
        }


@dataclass
class CppRawStmt(CppStatement):
    """Unclassified raw C++ text statement.

    Used for text output that cannot be categorized into other concrete types (e.g. goto, switch, comments).

    Attributes:
        raw_text: raw C++ text
    """
    raw_text: str = ""
    statement_type: str = "raw"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement_type": self.statement_type,
            "raw_text": self.raw_text,
        }


# ============================================================================
# Kismet Expression -> Structured C++ Statement Classifier
# ============================================================================

# Classification priority order: most specific to most general
# Each pattern tuple: (compiled_regex, factory_function)
_IF_PATTERN = re.compile(r'^if\s*\((.+)\)\s*\{?$')
_WHILE_PATTERN = re.compile(r'^while\s*\((.+)\)\s*\{?$')
_RETURN_PATTERN = re.compile(r'^return(?:\s+(.+))?$')
_ASSIGN_PATTERN = re.compile(r'^([\w][\w.>-]*)\s*=\s*(.+)$')
_CALL_PATTERN = re.compile(r'^([\w][\w:>-]*)\((.*)\)$')


def _classify_cpp_line(line: str) -> CppStatement:
    """Classify a single line of C++ text into a structured statement.

    Classification rules (by priority):
    1. if (cond) {  → CppIfStmt
    2. while (cond) { → CppWhileStmt
    3. return [expr] → CppReturnStmt
    4. lhs = rhs → CppAssignmentStmt
    5. func(args) / Class::Func(args) → CppCallStmt
    6. goto Label_N → CppRawStmt
    7. other → CppRawStmt

    Args:
        line: single line of C++ text (already stripped)

    Returns:
        Classified CppStatement instance
    """
    # 1. if statement
    m = _IF_PATTERN.match(line)
    if m:
        return CppIfStmt(condition=m.group(1))

    # 2. while statement
    m = _WHILE_PATTERN.match(line)
    if m:
        return CppWhileStmt(condition=m.group(1))

    # 3. return statement
    m = _RETURN_PATTERN.match(line)
    if m:
        return CppReturnStmt(value=m.group(1) or "")

    # 4. assignment statement: lhs = rhs
    #    classified as assignment only when top-level = exists and left side is not a function name
    m = _ASSIGN_PATTERN.match(line)
    if m:
        lhs = m.group(1)
        rhs = m.group(2)
        # Exclude false positives: if left side contains :: or -> followed by (, it is a call not an assignment
        # e.g. "Obj->Func()" should not match as assignment
        if '(' not in lhs and not rhs.lstrip().startswith('('):
            return CppAssignmentStmt(lhs=lhs, rhs=rhs)

    # 5. function call: Func(args) or Class::Func(args)
    m = _CALL_PATTERN.match(line)
    if m:
        method_name = m.group(1)
        args_str = m.group(2).strip()
        args = _split_args(args_str) if args_str else []
        return CppCallStmt(method_name=method_name, args=args)

    # 6. other: goto, switch, comments etc. all classified as CppRawStmt
    return CppRawStmt(raw_text=line)


def _split_args(args_str: str) -> List[str]:
    """Safely split a function argument string (handles nested brackets).

    Args:
        args_str: comma-separated argument string

    Returns:
        Argument list
    """
    if not args_str:
        return []

    result: List[str] = []
    depth = 0
    current: List[str] = []

    for ch in args_str:
        if ch in ('(', '<', '[', '{'):
            depth += 1
            current.append(ch)
        elif ch in (')', '>', ']', '}'):
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)

    if current:
        result.append(''.join(current).strip())

    return result


def kismet_to_cpp_body(
    expressions: List["KismetExpression"],
    translator: "KismetTranslator",
) -> List[CppStatement]:
    """Convert a list of Kismet expressions to a list of structured C++ statements.

    Iterate over each expression, call translator.line_cpp() to get C++ text,
    then classify the text into CppCallStmt, CppAssignmentStmt, CppIfStmt, etc.

    Args:
        expressions: Kismet expression list (from bytecode parsing)
        translator: KismetTranslator instance (with JumpAnalyzer structured detection)

    Returns:
        Structured CppStatement list
    """
    statements: List[CppStatement] = []

    for idx, expr in enumerate(expressions):
        text = translator.line_cpp(expr, index=idx)
        if not text or not text.strip():
            continue

        # Handle multi-line output (e.g. switch/case generated by EX_SwitchValue)
        lines = text.split("\n")
        for sub_line in lines:
            sub_line = sub_line.strip()
            if not sub_line:
                continue
            stmt = _classify_cpp_line(sub_line)
            statements.append(stmt)

    return statements

# ============================================================================
# C++ Class Skeleton IR Data Model (Per D-01, D-06)
# ============================================================================

@dataclass
class CppClassIR:
    """Complete C++ class skeleton IR (D-01, D-06).

    Attributes:
        name: C++ class name (e.g. "ABP_FirstPersonCharacter")
        parent_class: parent class name (e.g. "ACharacter")
        header_meta: header file metadata
        properties: property list (components + variables)
        methods: method list (available when populated)
        constructor: constructor data (available when populated)
    """
    name: str
    parent_class: str
    header_meta: CppHeaderMeta = field(default_factory=CppHeaderMeta)
    properties: List[CppProperty] = field(default_factory=list)
    methods: List["CppMethodIR"] = field(default_factory=list)
    constructor: Dict[str, List] = field(default_factory=lambda: {
        "component_creations": [],
        "component_assignments": [],
        "default_values": [],
    })  # to be populated

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict (D-06 format).

        Output structure:
        {
            "name": "...",
            "parent_class": "...",
            "header_meta": {...},
            "properties": [...],
            "methods": [],
            "constructor": {"component_creations": [], ...}
        }

        Returns:
            JSON-compatible dict structure
        """
        return {
            "name": self.name,
            "parent_class": self.parent_class,
            "header_meta": self.header_meta.to_dict(),
            "properties": [prop.to_dict() for prop in self.properties],
            "methods": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.methods],
            "constructor": self.constructor,  # empty dict
        }


# ============================================================================
# JSON IR Formatting Functions
# ============================================================================

def format_cpp_class_json(ir: CppClassIR, output_version: str = "1.0") -> Dict[str, Any]:
    """Format CppClassIR to JSON IR output (D-06).

    Output structure:
    {
        "cpp_class": {
            "name": "...",
            "parent_class": "...",
            "header_meta": {...},
            "properties": [...],
            "methods": [],
            "constructor": {...}
        },
        "output_version": "1.0"
    }

    Args:
        ir: CppClassIR data model
        output_version: output version string (default "1.0")

    Returns:
        Dict containing cpp_class and output_version
    """
    return {
        "cpp_class": ir.to_dict(),
        "output_version": output_version,
    }


# ============================================================================
# Export List
# ============================================================================

__all__ = [
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    # Method/Call IR
    "CppCallParameter",
    "CppMethodIR",
    "CppCallStatement",
    # Statement IR
    "CppStatement",
    "CppCallStmt",
    "CppAssignmentStmt",
    "CppIfStmt",
    "CppInlineExprStmt",
    "CppReturnStmt",
    "CppWhileStmt",
    "CppRawStmt",
    # Body builder
    "kismet_to_cpp_body",
]