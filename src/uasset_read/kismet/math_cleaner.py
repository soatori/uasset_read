"""Kismet 数学函数清理器 — 将 UKismetMathLibrary 等调用美化为人可读的 C++ 表达式。

从 translator.py 抽取，职责：将 Kismet 库函数调用转换为惯用 C++ 运算符/表达式。
"""
from __future__ import annotations


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
