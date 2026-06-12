"""
Kismet Expression → C++ Pseudocode Translator.

Translates KismetExpression AST into readable C++ pseudocode.

Provides:
- TypeRegistry: UE → C++ type mapping with metadata population
- MathFunctionCleaner: Beautifies UKismetMathLibrary::Add_IntInt(a,b) → a + b
- KismetTranslator: Central dispatcher with line_cpp() for all expression types
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.function_resolver import FunctionRefResolver
    from uasset_read.kismet.jump_analyzer import JumpAnalyzer
    from uasset_read.link.linker import PackageLinker


# ===========================================================================
# TypeRegistry — UE → C++ type mapping (Decision D-06, D-07)
# ===========================================================================

# UE Property type → C++ type mapping (aligned with GetPropertyType)
_UE_TO_CPP_TYPES: dict[str, str] = {
    "IntProperty": "int",
    "Int8Property": "int8",
    "Int16Property": "int16",
    "Int64Property": "int64",
    "UInt8Property": "uint8",
    "UInt16Property": "uint16",
    "UInt32Property": "uint32",
    "UInt64Property": "uint64",
    "FloatProperty": "float",
    "DoubleProperty": "double",
    "BoolProperty": "bool",
    "ByteProperty": "uint8",
    "StrProperty": "FString",
    "VerseStringProperty": "FString",
    "NameProperty": "FName",
    "TextProperty": "FText",
    "ObjectProperty": "UObject*",
    "ClassProperty": "UClass*",
    "StructProperty": "FStruct",
    "InterfaceProperty": "IInterface",
    "ArrayProperty": "TArray",
    "MapProperty": "TMap",
    "SetProperty": "TSet",
    "EnumProperty": "Enum",
    "DelegateProperty": "FScriptDelegate",
    "MulticastDelegateProperty": "FMulticastScriptDelegate",
    "SoftObjectProperty": "FSoftObjectPath",
    "SoftClassProperty": "FSoftClassPath",
    "WeakObjectProperty": "TWeakObjectPtr",
    "FieldPathProperty": "FFieldPath",
    "OptionalProperty": "TOptional",
}


class TypeRegistry:
    """
    Variable type registry for C++ pseudocode generation.

    Priority: explicitly registered type → metadata-inferred type → `auto`.
    """

    def __init__(self) -> None:
        self._types: dict[str, str] = {}

    def register_variable(self, name: str, cpp_type: str) -> None:
        """Register a variable with an explicit C++ type."""
        self._types[name] = cpp_type

    def lookup(self, name: str) -> str | None:
        """Look up the C++ type for a variable. Returns None if not found."""
        return self._types.get(name)

    def resolve_type(self, name: str) -> str:
        """Resolve type for a variable, falling back to 'auto' if unknown."""
        return self._types.get(name, "auto")

    def populate_from_metadata(self, metadata: dict) -> None:
        """
        Batch-initialize from BlueprintMetadata / BlueprintVariable data.

        Expected metadata format:
        {
            "variables": [
                {"name": "MyVar", "type": "IntProperty", ...},
                ...
            ],
            "functions": [
                {"name": "MyFunc", "params": [{"name": "Param1", "type": "FloatProperty"}], ...},
                ...
            ]
        }
        """
        # Process variables
        for var in metadata.get("variables", []):
            var_name = var.get("name")
            var_type = var.get("type", "")
            if var_name and var_type:
                cpp_type = _UE_TO_CPP_TYPES.get(var_type, var_type)
                self.register_variable(var_name, cpp_type)

        # Process function parameters and return values
        for func in metadata.get("functions", []):
            for param in func.get("params", []):
                param_name = param.get("name")
                param_type = param.get("type", "")
                if param_name and param_type:
                    cpp_type = _UE_TO_CPP_TYPES.get(param_type, param_type)
                    if param.get("flags") and "OutParm" in param.get("flags", ""):
                        cpp_type += "&"
                    self.register_variable(param_name, cpp_type)

            # Return value
            ret = func.get("return_value")
            if ret and ret.get("name"):
                ret_type = ret.get("type", "")
                cpp_type = _UE_TO_CPP_TYPES.get(ret_type, ret_type)
                self.register_variable(ret["name"], cpp_type)

    def ue_to_cpp(self, ue_type: str) -> str:
        """Convert a single UE property type to C++ type string."""
        return _UE_TO_CPP_TYPES.get(ue_type, ue_type)


# ===========================================================================
# MathFunctionCleaner — beautify Kismet library calls (Decision D-04, D-05)
# ===========================================================================

class MathFunctionCleaner:
    """
    Static cleaner that transforms Kismet library function calls
    into idiomatic C++ operators and expressions.

    Aligned with BlueprintDecompilerUtils.MathFunctionCleaner
    and FinalFunctionCleaner.
    """

    @staticmethod
    def clean(class_name: str, func_name: str, params: list[str]) -> str:
        """
        Clean a Kismet library function call.

        Args:
            class_name: UE class name (e.g., "KismetMathLibrary")
            func_name: Function name (e.g., "Add_IntInt")
            params: List of already-translated parameter strings

        Returns:
            Cleaned C++ expression string
        """
        params_list = params  # alias for brevity

        # --- KismetMathLibrary ---
        if class_name == "KismetMathLibrary":
            return MathFunctionCleaner._clean_math(func_name, params_list)

        # --- KismetStringLibrary ---
        if class_name == "KismetStringLibrary":
            return MathFunctionCleaner._clean_string(func_name, params_list)

        # --- KismetSystemLibrary ---
        if class_name == "KismetSystemLibrary":
            return MathFunctionCleaner._clean_system(func_name, params_list)

        # --- KismetInputLibrary, BlueprintGameplayTagLibrary, FortKismetLibrary, KismetTextLibrary ---
        if class_name in ("KismetInputLibrary", "BlueprintGameplayTagLibrary", "FortKismetLibrary", "KismetTextLibrary"):
            return MathFunctionCleaner._clean_misc(class_name, func_name, params_list)

        # --- KismetArrayLibrary (via FinalFunctionCleaner) ---
        if class_name == "KismetArrayLibrary":
            return MathFunctionCleaner._clean_array(func_name, params_list)

        # --- BlueprintMapLibrary ---
        if class_name == "BlueprintMapLibrary":
            return MathFunctionCleaner._clean_map(func_name, params_list)

        # --- BlueprintSetLibrary ---
        if class_name == "BlueprintSetLibrary":
            return MathFunctionCleaner._clean_set(func_name, params_list)

        # Fallback: ClassName::func_name(params)
        return f"{class_name}::{func_name}({', '.join(params_list)})"

    # --- Math library ---

    @staticmethod
    def _clean_math(func_name: str, p: list[str]) -> str:
        # Comparison
        if func_name.startswith("EqualEqual_"):
            if func_name.startswith("EqualEqual_ByteByte"):
                return f"((!{p[0]}) == (!{p[1]}))"
            return f"{p[0]} == {p[1]}"
        if func_name.startswith("NotEqualExactly_"):
            return f"({p[0]} != {p[1]})"
        if func_name.startswith("NotEqual_"):
            if func_name.startswith("NotEqual_ByteByte"):
                return f"((!{p[0]}) != (!{p[1]}))"
            return f"({p[0]} != {p[1]})"
        if func_name.startswith("LessEqual_"):
            return f"({p[0]} <= {p[1]})"
        if func_name.startswith("Less_"):
            return f"({p[0]} < {p[1]})"
        if func_name.startswith("GreaterEqual_"):
            return f"({p[0]} >= {p[1]})"
        if func_name.startswith("Greater_"):
            return f"({p[0]} > {p[1]})"

        # Arithmetic
        if func_name.startswith("Add_"):
            return f"{p[0]} + {p[1]}"
        if func_name.startswith("Subtract_"):
            return f"{p[0]} - {p[1]}"
        if func_name.startswith("Multiply_"):
            return f"({p[0]} * {p[1]})"
        if func_name.startswith("Divide_"):
            return f"({p[0]} / {p[1]})"
        if func_name.startswith("Percent_"):
            return f"({p[0]} % {p[1]})"

        # Bitwise
        if func_name.startswith("Xor_"):
            return f"({p[0]} ^ {p[1]})"
        if func_name.startswith("Or_"):
            return f"({p[0]} | {p[1]})"
        if func_name.startswith("And_"):
            return f"({p[0]} & {p[1]})"
        if func_name.startswith("Not_PreBool"):
            return f"!{p[0]}"
        if func_name.startswith("Not_"):
            return f"(~{p[0]})"

        # Boolean
        if func_name.startswith("BooleanAND"):
            return f"{p[0]} && {p[1]}"
        if func_name.startswith("BooleanNAND"):
            return f"!({p[0]} && {p[1]})"
        if func_name.startswith("BooleanOR"):
            return f"({p[0]} || {p[1]})"
        if func_name.startswith("BooleanXOR"):
            return f"{p[0]} ^ {p[1]}"
        if func_name.startswith("BooleanNOR"):
            return f"!({p[0]} || {p[1]})"

        # Compound assignment
        if func_name.startswith("AddEquals"):
            return f"({p[0]} += {p[1]})"
        if func_name.startswith("SubtractEquals"):
            return f"({p[0]} -= {p[1]})"
        if func_name.startswith("MultiplyEquals"):
            return f"({p[0]} *= {p[1]})"
        if func_name.startswith("DivideEquals"):
            return f"({p[0]} /= {p[1]})"

        # Math functions
        if func_name.startswith("Abs"):
            return f"({p[0]} < 0.0 ? -{p[0]} : {p[0]})"
        if func_name.startswith("Floor"):
            return f"Floor({p[0]})"
        if func_name.startswith("Ceil"):
            return f"Ceil({p[0]})"
        if func_name.startswith("Round") or func_name.startswith("RoundToInt"):
            return f"Round({p[0]})"
        if func_name.startswith("Sqrt"):
            return f"Sqrt({p[0]})"
        if func_name.startswith("Negate"):
            return f"-{p[0]}"
        if func_name == "Max":
            return f"(({p[0]} > {p[1]}) ? {p[0]} : {p[1]})"
        if func_name == "Min":
            return f"(({p[0]} < {p[1]}) ? {p[0]} : {p[1]})"
        if func_name.startswith("Clamp"):
            return f"(({p[0]} < {p[1]}) ? {p[1]} : (({p[0]} > {p[2]}) ? {p[2]} : {p[0]}))"
        if func_name.startswith("Lerp"):
            return f"{p[0]} + {p[2]} * ({p[1]} - {p[0]})"
        if func_name.startswith("FInterpTo"):
            return f"FInterpTo({p[0]}, {p[1]}, {p[2]}, {p[3]})"
        if func_name.startswith("FInterpEaseIn"):
            return f"FInterpEaseIn({p[0]}, {p[1]}, {p[2]}, {p[3]})"
        if func_name.startswith("FInterpEaseOut"):
            return f"FInterpEaseOut({p[0]}, {p[1]}, {p[2]}, {p[3]})"
        if func_name.startswith("CheckConstrainedFloat"):
            return f"{p[2]} < {p[0]} or {p[2]} > {p[1]}"
        if func_name.startswith("RandomFloatInRange"):
            return f"RandomFloatInRange({p[0]}, {p[1]})"
        if func_name.startswith("RandomFloat"):
            return f"RandomFloat()"
        if func_name.startswith("MapRangeClamped"):
            return f"MapRangeClamped({p[0]}, {p[1]}, {p[2]}, {p[3]}, {p[4]})"
        if func_name.startswith("NormalizeToRange"):
            return f"NormalizeToRange({p[0]}, {p[1]}, {p[2]})"

        # Type conversion
        if func_name.startswith("Conv_IntToBool"):
            return f"({p[0]} != 0)"
        if func_name.startswith("Conv_BoolToInt"):
            return f"({p[0]} ? 1 : 0)"
        if func_name.startswith("Conv_BoolToFloat"):
            return f"({p[0]} ? 1.0f : 0.0f)"
        if func_name.startswith("Conv_BoolToDouble"):
            return f"({p[0]} ? 1.0 : 0.0)"
        if func_name.startswith("Conv_BoolToByte"):
            return f"({p[0]} ? 1 : 0)"
        if func_name.startswith("Conv_FloatToDouble"):
            return f"((double){p[0]})"
        if func_name.startswith("Conv_DoubleToFloat"):
            return f"((float){p[0]})"
        if func_name.startswith("Conv_FloatToInt"):
            return f"((int32){p[0]})"
        if func_name.startswith("Conv_IntToFloat"):
            return f"((float){p[0]})"
        if func_name.startswith("Conv_IntToInt64"):
            return f"((int64){p[0]})"
        if func_name.startswith("Conv_Int64ToInt"):
            return f"((int32){p[0]})"
        if func_name.startswith("UncheckedConvertI32I64"):
            return f"{p[0]}"

        # Suffix conversions
        if func_name.endswith("ToDouble"):
            return f"((double){p[0]})"
        if func_name.endswith("ToFloat"):
            return f"((float){p[0]})"
        if func_name.endswith("ToInt64"):
            return f"((int64){p[0]})"
        if func_name.endswith("ToInt"):
            return f"((int32){p[0]})"
        if func_name.endswith("ToByte"):
            return f"((uint8){p[0]})"

        # Select (ternary)
        if func_name.startswith("Select"):
            return f"({p[2]} ? {p[0]} : {p[1]})"
        if func_name.startswith("IsValid"):
            return f"{p[0]} != nullptr"

        # Make constructors
        if func_name.startswith("MakeTransform"):
            return f"FTransform({p[0]}, {p[1]}, {p[2]})"
        if func_name.startswith("Conv_VectorToTransform"):
            return f"FTransform({p[0]})"
        if func_name.startswith("MakeVector2D"):
            return f"FVector2D({p[0]}, {p[1]})"
        if func_name.startswith("MakeVector"):
            return f"FVector({p[0]}, {p[1]}, {p[2]})"
        if func_name.endswith("ToVector"):
            return f"FVector((float){p[0]})"
        if func_name.startswith("MakeRotator"):
            return f"FRotator({p[0]}, {p[1]}, {p[2]})"
        if func_name.startswith("MakeTimespan"):
            return f"FTimespan({p[0]}, {p[1]}, {p[2]}, {p[4]} * 1000 * 1000)"
        if func_name.startswith("MakeColor"):
            return f"FLinearColor({p[0]}, {p[1]}, {p[2]}, {p[3]})"
        if func_name.startswith("ComposeRotators"):
            return f"FRotator(FQuat({p[0]}) * FQuat({p[1]}))"
        if func_name.endswith("ToLinearColor"):
            return f"FLinearColor({p[0]})"
        if func_name.startswith("Conv_NameToString"):
            return f"FString({p[0]})"
        if func_name.startswith("Conv_TextToString"):
            return f"FString({p[0]})"

        # Vector operations
        if func_name.startswith("Dot_") or func_name == "Dot_VectorVector":
            return f"Dot({p[0]}, {p[1]})"
        if func_name.startswith("Cross_") or func_name == "Cross_ProductVectorVector":
            return f"Cross({p[0]}, {p[1]})"
        if func_name.startswith("Normalize_") or func_name == "Normal_Vector":
            return f"Normalize({p[0]})"
        if func_name.startswith("VectorLength") or func_name.startswith("Length_"):
            return f"Length({p[0]})"
        if func_name.startswith("Distance_"):
            return f"Distance({p[0]}, {p[1]})"
        if func_name.startswith("Add_Vector") or func_name.startswith("Add_VectorVector"):
            return f"{p[0]} + {p[1]}"
        if func_name.startswith("Subtract_Vector"):
            return f"{p[0]} - {p[1]}"

        # Break functions
        if func_name == "BreakVector":
            return f"{p[1]} = {p[0]}.X;\n{p[2]} = {p[0]}.Y;\n{p[3]} = {p[0]}.Z"
        if func_name == "BreakVector2D":
            return f"{p[1]} = {p[0]}.X;\n{p[2]} = {p[0]}.Y"
        if func_name == "BreakRotator":
            return f"{p[1]} = {p[0]}.Roll;\n{p[2]} = {p[0]}.Pitch;\n{p[3]} = {p[0]}.Yaw"
        if func_name == "BreakTransform":
            return f"{p[1]} = {p[0]}.Location;\n{p[2]} = {p[0]}.Rotation;\n{p[3]} = {p[0]}.Scale"
        if func_name == "BreakColor":
            return f"{p[1]} = {p[0]}.R;\n{p[2]} = {p[0]}.G;\n{p[3]} = {p[0]}.B;\n{p[4]} = {p[0]}.A"

        return f"KismetMathLibrary::{func_name}({', '.join(p)})"

    # --- String library ---

    @staticmethod
    def _clean_string(func_name: str, p: list[str]) -> str:
        if func_name.startswith("EqualEqual_"):
            return f"{p[0]} == {p[1]}"
        if func_name.startswith("NotEqual_"):
            return f"({p[0]} != {p[1]})"

        if func_name.startswith("Conv_BoolToString"):
            return f"{p[0]} ? \"true\" : \"false\""
        if func_name.endswith("ToString"):
            return f"FString({p[0]})"
        if func_name.endswith("ToName"):
            return f"FName({p[0]})"
        if func_name.endswith("ToDouble"):
            return f"(double){p[0]}"
        if func_name.endswith("ToInt64"):
            return f"(int64){p[0]}"
        if func_name.endswith("ToInt"):
            return f"(int32){p[0]}"
        if func_name.endswith("ToByte"):
            return f"(uint8){p[0]}"
        if func_name.startswith("Concat_StrStr"):
            return " += ".join(p)
        if func_name.startswith("ParseIntoArray"):
            return f"{p[0]}.Split({p[1]}, /* removeEmpty = */ {p[2]})"
        if func_name.startswith("Contains"):
            return f"{p[0]}.Contains({p[1]}, /* bUseCase = */ {p[2]}, /* bSearchFromEnd = */ {p[3] if len(p) > 3 else 'false'})"
        if func_name.startswith("JoinStringArray"):
            return f"{p[0]}.Join({p[1]})"
        if func_name.startswith("Replace"):
            return f"{p[0]}.Replace({p[1]}, {p[2]}, /* SearchCase = */ {p[3] if len(p) > 3 else 'false'})"
        if func_name.startswith("StartsWith"):
            return f"{p[0]}.startswith({p[1]}, /* SearchCase = */ {p[2] if len(p) > 2 else 'false'})"
        if func_name.startswith("IsNumeric"):
            return f"{p[0]}.IsNumeric()"
        if func_name.startswith("Len"):
            return f"{p[0]}.Length"
        if func_name.startswith("Append"):
            return f"{p[0]} + {p[1]}"
        if func_name.startswith("Left"):
            return f"{p[0]}.Left({p[1]})"
        if func_name.startswith("Right"):
            return f"{p[0]}.Right({p[1]})"
        if func_name.startswith("Mid"):
            return f"{p[0]}.Mid({p[1]}, {p[2] if len(p) > 2 else '-1'})"
        if func_name.startswith("Trim"):
            return f"{p[0]}.Trim()"
        if func_name.startswith("ToUpper"):
            return f"{p[0]}.ToUpper()"
        if func_name.startswith("ToLower"):
            return f"{p[0]}.ToLower()"

        return f"KismetStringLibrary::{func_name}({', '.join(p)})"

    # --- System library ---

    @staticmethod
    def _clean_system(func_name: str, p: list[str]) -> str:
        if func_name.startswith("IsValid"):
            return f"{p[0]}"
        if func_name.startswith("Conv_SoftClassReferenceToClass"):
            return f"{p[0]}"
        if func_name.startswith("Conv_SoftObjectReferenceToObject"):
            return f"{p[0]}"
        if func_name.startswith("Conv_ObjectToSoftObjectReference"):
            return f"TSoftObjectPtr<UObject>({p[0]})"
        if func_name.startswith("Conv_SoftObjPathToSoftObjRef"):
            return f"TSoftObjectPtr<UObject>({p[0]})"
        if func_name.startswith("Conv_ClassToSoftClassReference"):
            return f"TSoftClassPtr<UObject>(*{p[0]})"
        if func_name.startswith("Conv_SoftClassPathToSoftClassRef"):
            return f"TSoftClassPtr<UObject>({p[0]})"
        if func_name.startswith("Delay") and len(p) >= 3:
            return f"Delay({p[1]}f);\n{p[2]}"
        if func_name.startswith("Make"):
            if len(p) == 1:
                return f"{p[0]}"

        return f"KismetSystemLibrary::{func_name}({', '.join(p)})"

    # --- Input/Tag/Text misc ---

    @staticmethod
    def _clean_misc(class_name: str, func_name: str, p: list[str]) -> str:
        if func_name.startswith("EqualEqual_"):
            return f"{p[0]} == {p[1]}"
        if func_name.startswith("NotEqual_"):
            return f"({p[0]} != {p[1]})"
        if func_name.endswith("ToText"):
            return f"FText({p[0]})"
        if func_name.endswith("ToString"):
            return f"FString({p[0]})"

        return f"{class_name}::{func_name}({', '.join(p)})"

    # --- Array library ---

    @staticmethod
    def _clean_array(func_name: str, p: list[str]) -> str:
        if func_name.startswith("Array_Length"):
            return f"{p[0]}.Length"
        if func_name.startswith("Array_IsNotEmpty"):
            return f"{p[0]}.Length > 0"
        if func_name.startswith("Array_IsEmpty"):
            return f"{p[0]}.Length == 0"
        if func_name.startswith("Array_LastIndex"):
            return f"{p[0]}.Length - 1"
        if func_name.startswith("Array_Clear"):
            return f"{p[0]}.Clear()"
        if func_name.startswith("Array_Identical"):
            return f"{p[0]} == {p[1]}"
        if func_name.startswith("Array_Remove"):
            return f"{p[0]}.Remove({p[1]})"
        if func_name.startswith("Array_Add"):
            return f"{p[0]}.Add({p[1]})"
        if func_name.startswith("Array_Get"):
            return f"{p[2]} = {p[0]}[{p[1]}]"
        if func_name.startswith("Array_Contains"):
            return f"{p[0]}.Contains({p[1]})"
        if func_name.startswith("Array_IsValidIndex"):
            return f"{p[0]}.IsValidIndex({p[1]})"
        if func_name.startswith("Array_Insert"):
            return f"{p[0]}.Insert({p[1]}, {p[2]})"
        if func_name.startswith("Array_Find"):
            return f"{p[0]}.Find({p[1]})"

        return f"KismetArrayLibrary::{func_name}({', '.join(p)})"

    # --- Map library ---

    @staticmethod
    def _clean_map(func_name: str, p: list[str]) -> str:
        if func_name.startswith("Map_Length"):
            return f"{p[0]}.Length"
        if func_name.startswith("Map_Remove"):
            return f"{p[0]}.Remove({p[1]})"
        if func_name.startswith("Map_Contains"):
            return f"{p[0]}.Contains({p[1]})"
        if func_name.startswith("Map_Get"):
            return f"{p[2]} = {p[0]}[{p[1]}]"
        if func_name.startswith("Map_Add"):
            return f"{p[0]}.Add({p[1]}, {p[2]})"
        if func_name.startswith("Map_IsValidIndex"):
            return f"{p[0]}.Contains({p[1]})"

        return f"BlueprintMapLibrary::{func_name}({', '.join(p)})"

    # --- Set library ---

    @staticmethod
    def _clean_set(func_name: str, p: list[str]) -> str:
        if func_name.startswith("Set_AddItems"):
            return f"{p[0]}.Add({p[1]})"
        if func_name.startswith("Set_Clear"):
            return f"{p[0]}.Clear()"
        if func_name.startswith("Set_Difference"):
            return f"{p[2]} = {p[0]} == {p[1]}"
        if func_name.startswith("Set_IsEmpty"):
            return f"{p[0]}.Length == 0"
        if func_name.startswith("Set_Length"):
            return f"{p[0]}.Length"

        return f"BlueprintSetLibrary::{func_name}({', '.join(p)})"


# ===========================================================================
# KismetTranslator — central line_cpp() dispatcher
# ===========================================================================

class KismetTranslator:
    """
    Translates a single KismetExpression to a one-line C++ pseudocode string.

    Uses match/case dispatch aligned with GetLineExpression switch.
    """

    def __init__(
        self,
        type_registry: TypeRegistry | None = None,
        linker: "PackageLinker | None" = None,
        expressions: list["KismetExpression"] | None = None,
    ):
        self.type_registry = type_registry or TypeRegistry()
        self._func_resolver: FunctionRefResolver | None = None
        # 统计计数器：跟踪 deprecated / instrumentation token
        self.skipped_tokens: dict[str, int] = {}
        if linker is not None:
            from uasset_read.kismet.function_resolver import FunctionRefResolver
            self._func_resolver = FunctionRefResolver(linker)
        self._jump_analyzer: "JumpAnalyzer | None" = None
        self._structured_indices: set[int] = set()
        if expressions is not None:
            from uasset_read.kismet.jump_analyzer import JumpAnalyzer
            self._jump_analyzer = JumpAnalyzer(expressions)
            self._structured_indices = self._build_structured_indices(expressions)

    def _build_structured_indices(self, expressions: list["KismetExpression"]) -> set[int]:
        """构建结构化控制流块中所有表达式的索引集合。

        委托给 JumpAnalyzer.get_structured_indices()，覆盖 while/for/if/switch 模式。
        这些索引对应的表达式在线性翻译中应被跳过或特殊处理。
        """
        if self._jump_analyzer is None:
            return set()
        return self._jump_analyzer.get_structured_indices()

    def line_cpp(self, expr: KismetExpression, index: int | None = None) -> str:
        """Translate a single KismetExpression to C++ pseudocode.

        Dispatches to category-specific _translate_* methods.
        """
        # Try each category in order; first match wins
        for handler in (
            self._translate_variables,
            self._translate_literals,
            self._translate_special,
            self._translate_return,
            self._translate_jumps,
            self._translate_casts,
            self._translate_context,
            self._translate_assignments,
            self._translate_functions,
            self._translate_containers,
            self._translate_structs,
            self._translate_delegates,
            self._translate_misc,
        ):
            result = handler(expr, index)
            if result is not None:
                return result
        return f"/* unknown: {type(expr).__name__} */"

    # -----------------------------------------------------------------------
    # Category translators — each returns str if handled, None otherwise
    # -----------------------------------------------------------------------

    def _translate_variables(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """变量引用：Local / Instance / Default / LocalOut / SparseData。"""
        from uasset_read.kismet.expressions import (
            EX_LocalVariable, EX_InstanceVariable, EX_DefaultVariable,
            EX_LocalOutVariable, EX_ClassSparseDataVariable,
        )
        if isinstance(expr, (EX_LocalVariable, EX_InstanceVariable,
                             EX_DefaultVariable, EX_LocalOutVariable,
                             EX_ClassSparseDataVariable)):
            var_ptr = expr.Variable
            if var_ptr is None:
                return "?"
            try:
                return str(var_ptr)
            except Exception:
                return "?"
        return None

    def _translate_literals(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """字面量：Int / Float / Byte / Bool / String / Object / Name / Vector。"""
        from uasset_read.kismet.expressions import (
            EX_IntConst, EX_FloatConst, EX_ByteConst, EX_IntConstByte,
            EX_Int64Const, EX_UInt64Const, EX_DoubleConst,
            EX_IntZero, EX_IntOne, EX_True, EX_False,
            EX_StringConst, EX_UnicodeStringConst, EX_TextConst, EX_SoftObjectConst,
            EX_VectorConst, EX_RotationConst, EX_TransformConst, EX_Vector3fConst,
            EX_ObjectConst, EX_NameConst,
        )
        # --- Integer literals ---
        if isinstance(expr, EX_IntConst):
            val = expr.Value
            if val > 0xFFFFFF and (val & 0xFFFFFF) == 0:
                return f"/* suspicious: 0x{val:08X} */"
            return str(val)
        if isinstance(expr, EX_IntZero):
            return "0"
        if isinstance(expr, EX_IntOne):
            return "1"
        if isinstance(expr, EX_Int64Const):
            return f"{expr.Value}LL"
        if isinstance(expr, EX_UInt64Const):
            return f"{expr.Value}ULL"
        # --- Float/Double ---
        if isinstance(expr, EX_FloatConst):
            return f"{expr.Value}f"
        if isinstance(expr, EX_DoubleConst):
            return str(expr.Value)
        # --- Byte ---
        if isinstance(expr, EX_ByteConst):
            return f"0x{expr.Value:02X}"
        if isinstance(expr, EX_IntConstByte):
            return str(expr.Value)
        # --- Boolean ---
        if isinstance(expr, EX_True):
            return "true"
        if isinstance(expr, EX_False):
            return "false"
        # --- String constants ---
        if isinstance(expr, (EX_StringConst, EX_UnicodeStringConst)):
            val = (str(expr.Value)
                   .replace("\r\n", "\\n").replace("\n", "\\n")
                   .replace('"', '\\"'))
            return f'"{val}"'
        if isinstance(expr, EX_TextConst):
            if hasattr(expr, 'Value') and expr.Value:
                inner = expr.Value
                if hasattr(inner, 'SourceString') and inner.SourceString:
                    val = (str(inner.SourceString)
                           .replace("\r\n", "\\n").replace("\n", "\\n")
                           .replace('"', '\\"'))
                    return f'FText("{val}")'
                if hasattr(inner, 'Text'):
                    val = (str(inner.Text)
                           .replace("\r\n", "\\n").replace("\n", "\\n")
                           .replace('"', '\\"'))
                    return f'FText("{val}")'
            return 'FText("")'
        # --- Object / Name ---
        if isinstance(expr, EX_ObjectConst):
            pkg_index = str(expr.Value) if expr.Value else ""
            if "'" in pkg_index:
                parts = pkg_index.split("'", 1)
                type_name = parts[0]
                path = parts[1].rstrip("'")
                class_pkg = f"U{type_name}"
                return f'FindObject<{class_pkg}>(nullptr, "{path}")'
            return f'FindObject<UObject>(nullptr, "{pkg_index}")'
        if isinstance(expr, EX_NameConst):
            val = str(expr.Value) if expr.Value else ""
            return f'FName("{val}")'
        if isinstance(expr, EX_SoftObjectConst):
            inner = self.line_cpp(expr.Value) if hasattr(expr, 'Value') and expr.Value else '""'
            return f"FSoftObjectPath({inner})"
        # --- Vector / Rotation / Transform ---
        if isinstance(expr, EX_Vector3fConst):
            v = expr.Value
            return f"FVector3f({v.X}, {v.Y}, {v.Z})"
        if isinstance(expr, EX_VectorConst):
            v = expr.Value
            return f"FVector({v.X}, {v.Y}, {v.Z})"
        if isinstance(expr, EX_RotationConst):
            v = expr.Value
            return f"FRotator({v.Pitch}, {v.Roll}, {v.Yaw})"
        if isinstance(expr, EX_TransformConst):
            v = expr.Value
            return (
                f"FTransform(FQuat({v.Rotation.X}, {v.Rotation.Y}, "
                f"{v.Rotation.Z}, {v.Rotation.W}), "
                f"FVector({v.Translation.X}, {v.Translation.Y}, "
                f"{v.Translation.Z}), "
                f"FVector({v.Scale3D.X}, {v.Scale3D.Y}, {v.Scale3D.Z}))"
            )
        return None

    def _translate_special(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """特殊关键字：Self / Nothing / EndOfScript / RTFM。"""
        from uasset_read.kismet.expressions import (
            EX_Self, EX_NoObject, EX_NoInterface,
            EX_Nothing, EX_NothingInt32, EX_EndOfScript,
            EX_EndFunctionParms, EX_EndParmValue,
            EX_EndArray, EX_EndArrayConst, EX_EndMap,
            EX_EndMapConst, EX_EndSet, EX_EndSetConst,
            EX_EndStructConst, EX_PushExecutionFlow,
            EX_AutoRtfmTransact, EX_AutoRtfmStopTransact, EX_AutoRtfmAbortIfNot,
        )
        if isinstance(expr, EX_Self):
            return "this"
        if isinstance(expr, (EX_NoObject, EX_NoInterface)):
            return "nullptr"
        if isinstance(expr, (EX_Nothing, EX_NothingInt32, EX_EndOfScript,
                             EX_EndFunctionParms, EX_EndParmValue,
                             EX_EndArray, EX_EndArrayConst, EX_EndMap,
                             EX_EndMapConst, EX_EndSet, EX_EndSetConst,
                             EX_EndStructConst, EX_PushExecutionFlow)):
            return ""
        # RTFM
        if isinstance(expr, EX_AutoRtfmTransact):
            return "/* RTFM: begin transaction */"
        if isinstance(expr, EX_AutoRtfmStopTransact):
            return "/* RTFM: end transaction */"
        if isinstance(expr, EX_AutoRtfmAbortIfNot):
            return "/* RTFM: abort if condition */"
        return None

    def _translate_return(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """EX_Return。"""
        from uasset_read.kismet.expressions import EX_Return, EX_Nothing, EX_NothingInt32
        if isinstance(expr, EX_Return):
            ret_expr = (
                expr.ReturnExpression
                if hasattr(expr, 'ReturnExpression')
                else getattr(expr, 'Value', None)
            )
            if ret_expr is None:
                return "return"
            if isinstance(ret_expr, (EX_Nothing, EX_NothingInt32)):
                return "return"
            return f"return {self.line_cpp(ret_expr)}"
        return None

    def _translate_jumps(
        self, expr: KismetExpression, index: int | None,
    ) -> str | None:
        """跳转 / 执行流控制：JumpIfNot / Jump / ComputedJump / Skip / Pop。"""
        from uasset_read.kismet.expressions import (
            EX_Jump, EX_JumpIfNot, EX_Skip, EX_ComputedJump,
            EX_SkipOffsetConst, EX_PopExecutionFlow, EX_PopExecutionFlowIfNot,
        )
        if isinstance(expr, EX_JumpIfNot):
            cond = (self.line_cpp(expr.BooleanExpression)
                    if hasattr(expr, 'BooleanExpression') and expr.BooleanExpression
                    else "?")
            offset = (expr.CodeOffset if hasattr(expr, 'CodeOffset')
                      else getattr(expr, 'Value', 0))
            if self._jump_analyzer is not None and index is not None:
                if self._jump_analyzer.detect_for_pattern(index) is not None:
                    return f"for ({cond}) {{"
                if self._jump_analyzer.detect_while_pattern(index) is not None:
                    return f"while ({cond}) {{"
                if self._jump_analyzer.detect_if_else_pattern(index) is not None:
                    return f"if ({cond}) {{"
            return f"if (!{cond}) goto Label_{offset};"
        if isinstance(expr, EX_Jump):
            offset = (expr.CodeOffset if hasattr(expr, 'CodeOffset')
                      else getattr(expr, 'Value', 0))
            if self._jump_analyzer is not None and index is not None:
                if self._jump_analyzer.is_while_backjump(index):
                    return ""
            return f"goto Label_{offset};"
        if isinstance(expr, EX_ComputedJump):
            var = (self.line_cpp(expr.CodeOffsetExpression)
                   if hasattr(expr, 'CodeOffsetExpression') and expr.CodeOffsetExpression
                   else "?")
            return f"goto {var};"
        if isinstance(expr, EX_Skip):
            offset = expr.CodeOffset if hasattr(expr, 'CodeOffset') else expr.Value
            return f"goto Label_{offset};"
        if isinstance(expr, EX_SkipOffsetConst):
            offset = expr.Value if hasattr(expr, 'Value') else 0
            return f"goto Label_{offset};"
        if isinstance(expr, EX_PopExecutionFlow):
            if self._jump_analyzer is not None and index is not None:
                if index in self._structured_indices:
                    return "}"
            return "return;"
        if isinstance(expr, EX_PopExecutionFlowIfNot):
            cond = (self.line_cpp(expr.BooleanExpression)
                    if hasattr(expr, 'BooleanExpression') else "?")
            return f"if (!{cond}) return;"
        return None

    def _translate_casts(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """类型转换：Cast / MetaCast / DynamicCast 等。"""
        from uasset_read.kismet.expressions import (
            EX_Cast, EX_MetaCast, EX_DynamicCast,
            EX_ObjToInterfaceCast, EX_CrossInterfaceCast, EX_InterfaceToObjCast,
        )
        if isinstance(expr, EX_Cast):
            target = self.line_cpp(expr.Target) if hasattr(expr, 'Target') else "?"
            from uasset_read.kismet.tokens import ECastToken
            conversion = getattr(expr, 'ConversionType', None)
            type_map = {
                ECastToken.CST_ObjectToInterface: "Interface",
                ECastToken.CST_ObjectToBool: "bool",
                ECastToken.CST_ObjectToBool2: "bool",
                ECastToken.CST_InterfaceToBool: "bool",
                ECastToken.CST_InterfaceToBool2: "bool",
                ECastToken.CST_DoubleToFloat: "float",
                ECastToken.CST_FloatToDouble: "double",
            }
            cpp_type = type_map.get(conversion, "auto") if conversion is not None else "auto"
            return f"static_cast<{cpp_type}>({target})"
        if isinstance(expr, (EX_MetaCast, EX_DynamicCast, EX_ObjToInterfaceCast,
                             EX_CrossInterfaceCast, EX_InterfaceToObjCast)):
            target = self.line_cpp(expr.Target) if hasattr(expr, 'Target') else "?"
            class_ptr = getattr(expr, 'ClassPtr', None)
            if class_ptr and hasattr(class_ptr, 'Name'):
                class_name = str(class_ptr.Name)
                if not class_name.startswith(('U', 'A', 'F', 'I')):
                    class_name = f"U{class_name}"
            else:
                class_name = "UObject"
            return f"Cast<{class_name}>({target})"
        return None

    def _translate_context(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """上下文表达式：Context / ClassContext / InterfaceContext / StructMemberContext。"""
        from uasset_read.kismet.expressions import (
            EX_Context, EX_Context_FailSilent, EX_ClassContext,
            EX_InterfaceContext, EX_StructMemberContext,
        )
        if isinstance(expr, (EX_Context, EX_Context_FailSilent)):
            obj = (self.line_cpp(expr.ObjectExpression)
                   if hasattr(expr, 'ObjectExpression') and expr.ObjectExpression else "?")
            ctx_expr = (self.line_cpp(expr.ContextExpression)
                        if hasattr(expr, 'ContextExpression') and expr.ContextExpression else "")
            func_name = ctx_expr.split("::")[-1] if "::" in ctx_expr else ctx_expr
            if isinstance(expr, EX_Context_FailSilent):
                return f"if ({obj}) {obj}->{func_name}"
            return f"{obj}->{func_name}"
        if isinstance(expr, EX_ClassContext):
            obj = (self.line_cpp(expr.ObjectExpression)
                   if hasattr(expr, 'ObjectExpression') and expr.ObjectExpression else "?")
            ctx_expr = (self.line_cpp(expr.ContextExpression)
                        if hasattr(expr, 'ContextExpression') and expr.ContextExpression else "")
            func_name = ctx_expr.split("::")[-1] if "::" in ctx_expr else ctx_expr
            return f"{obj}->{func_name}"
        if isinstance(expr, EX_InterfaceContext):
            return (self.line_cpp(expr.InterfaceValue)
                    if hasattr(expr, 'InterfaceValue') and expr.InterfaceValue else "?")
        if isinstance(expr, EX_StructMemberContext):
            prop = str(expr.Property) if hasattr(expr, 'Property') else "?"
            struct = (self.line_cpp(expr.StructExpression)
                      if hasattr(expr, 'StructExpression') and expr.StructExpression else "?")
            return f"{struct}.{prop}"
        return None

    def _translate_assignments(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """赋值：Let / LetBool / LetObj / LetValueOnPersistentFrame 等。"""
        from uasset_read.kismet.expressions import (
            EX_Let, EX_LetBase, EX_LetBool, EX_LetDelegate,
            EX_LetObj, EX_LetWeakObjPtr, EX_LetMulticastDelegate,
            EX_LetValueOnPersistentFrame,
        )
        if isinstance(expr, (EX_Let, EX_LetBase, EX_LetBool, EX_LetDelegate,
                             EX_LetObj, EX_LetWeakObjPtr, EX_LetMulticastDelegate)):
            var = (self.line_cpp(expr.Variable)
                   if hasattr(expr, 'Variable') and expr.Variable else "?")
            assignment = (self.line_cpp(expr.Assignment)
                          if hasattr(expr, 'Assignment') and expr.Assignment else "?")
            return f"{var} = {assignment}"
        if isinstance(expr, EX_LetValueOnPersistentFrame):
            assignment = (self.line_cpp(expr.AssignmentExpression)
                          if hasattr(expr, 'AssignmentExpression') and expr.AssignmentExpression
                          else "?")
            dest = str(expr.DestinationProperty) if hasattr(expr, 'DestinationProperty') else "?"
            var_name = f"UberGraphFrame->{dest}" if "K2Node_" in dest else dest
            return f"{var_name} = {assignment}"
        return None

    def _translate_functions(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """函数调用：FinalFunction / CallMath / VirtualFunction / CallMulticastDelegate。"""
        from uasset_read.kismet.expressions import (
            EX_FinalFunction, EX_CallMath, EX_LocalFinalFunction,
            EX_VirtualFunction, EX_LocalVirtualFunction,
            EX_CallMulticastDelegate, EX_InstanceDelegate,
        )
        if isinstance(expr, (EX_FinalFunction, EX_CallMath)):
            params_list = []
            if hasattr(expr, 'Parameters') and expr.Parameters:
                for param in expr.Parameters:
                    p_str = self.line_cpp(param)
                    if p_str:
                        params_list.append(p_str)
            stack_node = getattr(expr, 'StackNode', 0)
            resolved_class, resolved_func = self._resolve_stack_node(stack_node)
            if isinstance(expr, EX_CallMath):
                cn = resolved_class or (f"Function_{stack_node}" if isinstance(stack_node, int) else str(stack_node))
                fn = resolved_func or f"Call_{stack_node}"
                return MathFunctionCleaner.clean(cn, fn, params_list)
            if isinstance(expr, EX_LocalFinalFunction):
                if resolved_class is not None and resolved_func is not None:
                    is_local = (self._func_resolver.is_local_function(stack_node)
                                if self._func_resolver and isinstance(stack_node, int)
                                else False)
                    if is_local:
                        return f"this->{resolved_func}({', '.join(params_list)})"
                    return f"{resolved_class}::{resolved_func}({', '.join(params_list)})"
                return f"LocalFunction_{stack_node}({', '.join(params_list)})"
            if resolved_class is not None and resolved_func is not None:
                return f"{resolved_class}::{resolved_func}({', '.join(params_list)})"
            return f"Function_{stack_node}({', '.join(params_list)})"
        if isinstance(expr, (EX_VirtualFunction, EX_LocalVirtualFunction)):
            func_name = (expr.VirtualFunctionName.Text
                         if hasattr(expr, 'VirtualFunctionName')
                         and hasattr(expr.VirtualFunctionName, 'Text')
                         else str(getattr(expr, 'VirtualFunctionName', '?')))
            params_list = []
            if hasattr(expr, 'Parameters') and expr.Parameters:
                for param in expr.Parameters:
                    p_str = self.line_cpp(param)
                    if p_str:
                        params_list.append(p_str)
            class_name = None
            if self._func_resolver and func_name and func_name != '?':
                class_name = self._func_resolver.resolve_virtual_function_class(func_name)
            prefix = f"{class_name}::" if class_name else ""
            return f"{prefix}{func_name}({', '.join(params_list)})"
        if isinstance(expr, EX_CallMulticastDelegate):
            params_list = []
            if hasattr(expr, 'Parameters') and expr.Parameters:
                for param in expr.Parameters:
                    p_str = self.line_cpp(param)
                    if p_str:
                        params_list.append(p_str)
            delegate = (self.line_cpp(expr.Delegate)
                        if hasattr(expr, 'Delegate') and expr.Delegate else "?")
            stack_node = getattr(expr, 'StackNode', 0)
            _, resolved_func = self._resolve_stack_node(stack_node)
            if resolved_func is not None:
                return f"{delegate}->{resolved_func}({', '.join(params_list)})"
            return f"{delegate}->Broadcast({', '.join(params_list)})"
        if isinstance(expr, EX_InstanceDelegate):
            fn = getattr(expr, 'FunctionName', '?')
            return f'"{fn}"'
        return None

    def _translate_containers(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """容器：SetArray / ArrayConst / SetMap / MapConst / SetSet / SetConst / ArrayGetByRef。"""
        from uasset_read.kismet.expressions import (
            EX_SetArray, EX_ArrayConst, EX_SetMap, EX_MapConst,
            EX_SetSet, EX_SetConst, EX_ArrayGetByRef,
        )
        if isinstance(expr, EX_SetArray):
            var = (self.line_cpp(expr.AssigningProperty)
                   if hasattr(expr, 'AssigningProperty') and expr.AssigningProperty else "?")
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            return f"{var} = [{', '.join(values)}]"
        if isinstance(expr, EX_ArrayConst):
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            inner_type = (str(expr.InnerProperty)
                          if hasattr(expr, 'InnerProperty') and expr.InnerProperty else "auto")
            return f"TArray<{inner_type}>{{{', '.join(values)}}}"
        if isinstance(expr, EX_SetMap):
            target = (self.line_cpp(expr.MapProperty)
                      if hasattr(expr, 'MapProperty') and expr.MapProperty else "?")
            if not hasattr(expr, 'Elements') or not expr.Elements:
                return f"{target} = TMap {{ }}"
            pairs = self._extract_map_pairs(expr.Elements)
            return f"{target} = TMap {{ {', '.join(pairs)} }}"
        if isinstance(expr, EX_MapConst):
            if not hasattr(expr, 'Elements') or not expr.Elements:
                return "TMap { }"
            pairs = self._extract_map_pairs(expr.Elements)
            return f"TMap {{ {', '.join(pairs)} }}"
        if isinstance(expr, EX_SetSet):
            target = (self.line_cpp(expr.SetProperty)
                      if hasattr(expr, 'SetProperty') and expr.SetProperty else "?")
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            return f"{target} = TSet{{{', '.join(values)}}}"
        if isinstance(expr, EX_SetConst):
            values = [v for el in (expr.Elements or []) if (v := self.line_cpp(el))]
            return f"TSet{{{', '.join(values)}}}"
        if isinstance(expr, EX_ArrayGetByRef):
            arr = (self.line_cpp(expr.ArrayVariable)
                   if hasattr(expr, 'ArrayVariable') and expr.ArrayVariable else "?")
            idx = (self.line_cpp(expr.ArrayIndex)
                   if hasattr(expr, 'ArrayIndex') and expr.ArrayIndex else "?")
            return f"{arr}[{idx}]"
        return None

    def _translate_structs(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """结构体常量 / 位字段 / 属性常量。"""
        from uasset_read.kismet.expressions import EX_StructConst, EX_BitFieldConst, EX_PropertyConst
        if isinstance(expr, EX_StructConst):
            struct_name = (str(expr.Struct.Name)
                           if hasattr(expr, 'Struct') and hasattr(expr.Struct, 'Name')
                           else "Struct")
            values = [v for prop in (expr.Properties or []) if (v := self.line_cpp(prop))]
            return f"F{struct_name}{{{', '.join(values)}}}"
        if isinstance(expr, EX_BitFieldConst):
            return str(expr.ConstValue) if hasattr(expr, 'ConstValue') else "0"
        if isinstance(expr, EX_PropertyConst):
            return str(expr.Property) if hasattr(expr, 'Property') else "?"
        return None

    def _translate_delegates(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """委托操作：Add / Clear / Bind / Remove multicast delegate。"""
        from uasset_read.kismet.expressions import (
            EX_AddMulticastDelegate, EX_ClearMulticastDelegate,
            EX_BindDelegate, EX_RemoveMulticastDelegate,
            EX_Context, EX_Context_FailSilent,
        )
        if isinstance(expr, EX_AddMulticastDelegate):
            delegate = (self.line_cpp(expr.Delegate)
                        if hasattr(expr, 'Delegate') and expr.Delegate else "?")
            to_add = (self.line_cpp(expr.DelegateToAdd)
                      if hasattr(expr, 'DelegateToAdd') and expr.DelegateToAdd else "?")
            return f"{delegate}->Add({to_add})"
        if isinstance(expr, EX_ClearMulticastDelegate):
            delegate = (self.line_cpp(expr.DelegateToClear)
                        if hasattr(expr, 'DelegateToClear') and expr.DelegateToClear else "?")
            return f"{delegate}.Clear()"
        if isinstance(expr, EX_BindDelegate):
            delegate = (self.line_cpp(expr.Delegate)
                        if hasattr(expr, 'Delegate') and expr.Delegate else "?")
            obj = (self.line_cpp(expr.ObjectTerm)
                   if hasattr(expr, 'ObjectTerm') and expr.ObjectTerm else "?")
            fn = (expr.FunctionName.Text
                  if hasattr(expr, 'FunctionName') and hasattr(expr.FunctionName, 'Text')
                  else "?")
            return f'{delegate}->BindUFunction({obj}, FName("{fn}"))'
        if isinstance(expr, EX_RemoveMulticastDelegate):
            delegate = (self.line_cpp(expr.Delegate)
                        if hasattr(expr, 'Delegate') and expr.Delegate else "?")
            to_remove = (self.line_cpp(expr.DelegateToAdd)
                         if hasattr(expr, 'DelegateToAdd') and expr.DelegateToAdd else "?")
            sep = ("->" if isinstance(expr.Delegate, (EX_Context, EX_Context_FailSilent))
                   else "." if hasattr(expr, 'Delegate') and expr.Delegate else ".")
            return f"{delegate}{sep}RemoveDelegate({to_remove})"
        return None

    def _translate_misc(
        self, expr: KismetExpression, _index: int | None,
    ) -> str | None:
        """SwitchValue / Assert / Deprecated / Breakpoint / FieldPath。"""
        from uasset_read.kismet.expressions import (
            EX_SwitchValue, EX_Assert,
            EX_DeprecatedOp4A, EX_Breakpoint, EX_Tracepoint, EX_WireTracepoint,
            EX_InstrumentationEvent, EX_FieldPathConst,
        )
        if isinstance(expr, EX_SwitchValue):
            idx = (self.line_cpp(expr.IndexTerm)
                   if hasattr(expr, 'IndexTerm') and expr.IndexTerm else "?")
            if hasattr(expr, 'Cases') and len(expr.Cases) == 2:
                case0 = self.line_cpp(expr.Cases[0].CaseTerm)
                case1 = self.line_cpp(expr.Cases[1].CaseTerm)
                return f"{idx} ? {case1} : {case0}"
            lines = [f"switch ({idx}) {{"]
            if hasattr(expr, 'Cases'):
                for case_item in expr.Cases:
                    case_idx = (self.line_cpp(case_item.CaseIndexValueTerm)
                                if hasattr(case_item, 'CaseIndexValueTerm') else "?")
                    case_val = self.line_cpp(case_item.CaseTerm)
                    lines.append(f"  case {case_idx}: return {case_val}; break;")
            default = (self.line_cpp(expr.DefaultTerm)
                       if hasattr(expr, 'DefaultTerm') and expr.DefaultTerm else "?")
            lines.append(f"  default: return {default};")
            lines.append("}")
            return "\n".join(lines)
        if isinstance(expr, EX_Assert):
            cond = str(expr.AssertExpression) if hasattr(expr, 'AssertExpression') else "?"
            return f"assert({cond})"
        if isinstance(expr, EX_DeprecatedOp4A):
            self.skipped_tokens["EX_DeprecatedOp4A"] = self.skipped_tokens.get("EX_DeprecatedOp4A", 0) + 1
            return ""
        if isinstance(expr, (EX_Breakpoint, EX_Tracepoint, EX_WireTracepoint)):
            name = type(expr).__name__
            self.skipped_tokens[name] = self.skipped_tokens.get(name, 0) + 1
            return ""
        if isinstance(expr, EX_InstrumentationEvent):
            self.skipped_tokens["EX_InstrumentationEvent"] = self.skipped_tokens.get("EX_InstrumentationEvent", 0) + 1
            return ""
        if isinstance(expr, EX_FieldPathConst):
            return str(expr.Value) if hasattr(expr, 'Value') else "?"
        return None

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _resolve_stack_node(self, stack_node: int) -> tuple[str | None, str | None]:
        """通过 FunctionRefResolver 解析 StackNode → (class_name, func_name)。"""
        if self._func_resolver and isinstance(stack_node, int) and stack_node != 0:
            result = self._func_resolver.resolve(stack_node)
            if result is not None:
                return result
        return None, None

    def _extract_map_pairs(self, elements: list) -> list[str]:
        """从键值交替的元素列表中提取 "key: val" 字符串对。"""
        pairs: list[str] = []
        for i in range(0, len(elements), 2):
            if i + 1 < len(elements):
                key = self.line_cpp(elements[i])
                val = self.line_cpp(elements[i + 1])
                pairs.append(f"{key}: {val}")
        return pairs


# ===========================================================================
# Module-level convenience functions (D-01 dual API)
# ===========================================================================

def line_cpp(expr: "KismetExpression") -> str:
    """
    Module-level convenience wrapper for KismetTranslator.line_cpp().

    Usage:
        from uasset_read.kismet import line_cpp
        from uasset_read.kismet.expressions import EX_IntConst

        expr = EX_IntConst(StatementIndex=0, Value=42)
        print(line_cpp(expr))  # "42"
    """
    translator = KismetTranslator()
    return translator.line_cpp(expr)


# Export module-level constants
UE_TYPE_MAP = _UE_TO_CPP_TYPES
