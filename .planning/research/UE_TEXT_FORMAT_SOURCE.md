# UE文本格式生成源码研究

**资产**: BP_FirstPersonCharacter.uasset
**日期**: 2026-05-04
**目的**: 定位UE编辑器复制蓝图节点的源码，理解文本格式生成逻辑，指导uasset_read解析实现

---

## 1. 源码定位

### 1.1 核心文件路径

| 文件 | 路径 | 功能 |
|------|------|------|
| BPGraphClipboardData.cpp | Engine/Source/Editor/Kismet/Private/ | 蓝图复制粘贴入口 |
| EdGraphUtilities.cpp | Engine/Source/Editor/UnrealEd/Private/ | ExportNodesToText函数 |
| EdGraphNode.cpp | Engine/Source/Runtime/Engine/Private/EdGraph/ | 节点ExportCustomProperties |
| EdGraphPin.cpp | Engine/Source/Runtime/Engine/Private/EdGraph/ | Pin ExportTextItem |

### 1.2 调用链

```
用户Ctrl+C → FBPGraphClipboardData::SetFromGraph()
           → FEdGraphUtilities::ExportNodesToText()
           → UExporter::ExportToOutputDevice()
           → UEdGraphNode::ExportCustomProperties()
           → UEdGraphPin::ExportTextItem()
```

---

## 2. ExportNodesToText（EdGraphUtilities.cpp:458-481）

```cpp
void FEdGraphUtilities::ExportNodesToText(TSet<UObject*> NodesToExport, FString& ExportedText)
{
    // Clear the mark state for saving.
    UnMarkAllObjects(EObjectMark(OBJECTMARK_TagExp | OBJECTMARK_TagImp));

    FStringOutputDevice Archive;
    const FExportObjectInnerContext Context;

    // Export each of the selected nodes
    UObject* LastOuter = NULL;
    for (TSet<UObject*>::TConstIterator NodeIt(NodesToExport); NodeIt; ++NodeIt)
    {
        UObject* Node = *NodeIt;

        // The nodes should all be from the same scope
        UObject* ThisOuter = Node->GetOuter();
        check((LastOuter == ThisOuter) || (LastOuter == NULL));
        LastOuter = ThisOuter;

        UExporter::ExportToOutputDevice(&Context, Node, NULL, Archive, TEXT("copy"), 0,
            PPF_ExportsNotFullyQualified|PPF_Copy|PPF_Delimited, false, ThisOuter);
    }

    ExportedText = Archive;
}
```

**关键标志**：
- `PPF_ExportsNotFullyQualified` — 导出相对路径
- `PPF_Copy` — 复制模式
- `PPF_Delimited` — 使用逗号分隔

---

## 3. UEdGraphNode::ExportCustomProperties（EdGraphNode.cpp:751-761）

```cpp
void UEdGraphNode::ExportCustomProperties(FOutputDevice& Out, uint32 Indent)
{
    Super::ExportCustomProperties(Out, Indent);

    for (const UEdGraphPin* Pin : Pins)
    {
        FString PinString;
        Pin->ExportTextItem(PinString, PPF_Delimited);
        Out.Logf(TEXT("%sCustomProperties Pin %s\r\n"), FCString::Spc(Indent), *PinString);
    }
}
```

**输出格式**：
```
CustomProperties Pin (PinId=XXX,PinName="execute",...)
CustomProperties Pin (PinId=YYY,PinName="then",...)
```

---

## 4. UEdGraphPin::ExportTextItem（EdGraphPin.cpp:1077-1255）

### 4.1 完整导出逻辑

```cpp
bool UEdGraphPin::ExportTextItem(FString& ValueStr, int32 PortFlags) const
{
    ValueStr += "(";

    // 1. PinId (必须)
    ValueStr += PinHelpers::PinIdName + TEXT("=");
    PinId.ExportTextItem(ValueStr, FGuid(), nullptr, PortFlags, nullptr);
    ValueStr += PinHelpers::ExportTextPropDelimiter;  // ','

    // 2. PinName (非默认时)
    if (PinName != DefaultPin.PinName)
    {
        ValueStr += PinHelpers::PinNameName + TEXT("=");
        NamePropCDO->ExportTextItem_Direct(ValueStr, &PinName, nullptr, nullptr, PortFlags, nullptr);
        ValueStr += PinHelpers::ExportTextPropDelimiter;
    }

    // 3. Direction (非默认时)
    if (Direction != DefaultPin.Direction)
    {
        const FString DirectionString = UEnum::GetValueAsString(TEXT("/Script/Engine.EEdGraphPinDirection"), Direction);
        ValueStr += PinHelpers::DirectionName + TEXT("=");
        StrPropCDO->ExportTextItem_Direct(ValueStr, &DirectionString, nullptr, nullptr, PortFlags, nullptr);
        ValueStr += PinHelpers::ExportTextPropDelimiter;
    }

    // 4. PinType结构体 (反射遍历所有属性)
    for (TFieldIterator<FProperty> FieldIt(FEdGraphPinType::StaticStruct()); FieldIt; ++FieldIt)
    {
        FProperty* Prop = *FieldIt;
        if (Prop->ShouldPort())
        {
            FString PropertyStr;
            const uint8* PropertyAddr = Prop->ContainerPtrToValuePtr<uint8>(&PinType);
            const uint8* DefaultAddr = Prop->ContainerPtrToValuePtr<uint8>(&DefaultPin.PinType);
            Prop->ExportTextItem_Direct(PropertyStr, PropertyAddr, DefaultAddr, NULL, PortFlags, nullptr);

            if (!PropertyStr.IsEmpty())
            {
                ValueStr += PinHelpers::PinTypeName + TEXT(".") + FieldIt->GetName() + "=" + PropertyStr;
                ValueStr += PinHelpers::ExportTextPropDelimiter;
            }
        }
    }

    // 5. DefaultValue (非默认时)
    if (DefaultValue != DefaultPin.DefaultValue)
    {
        ValueStr += PinHelpers::DefaultValueName + TEXT("=");
        StrPropCDO->ExportTextItem_Direct(ValueStr, &DefaultValue, nullptr, nullptr, PortFlags, nullptr);
        ValueStr += PinHelpers::ExportTextPropDelimiter;
    }

    // 6. LinkedTo数组
    if (LinkedTo.Num() > 0)
    {
        ValueStr += PinHelpers::LinkedToName + TEXT("=") + UEdGraphPin::ExportText_PinArray(LinkedTo);
        ValueStr += PinHelpers::ExportTextPropDelimiter;
    }

    // 7. SubPins数组
    if (SubPins.Num() > 0)
    {
        ValueStr += PinHelpers::SubPinsName + TEXT("=") + UEdGraphPin::ExportText_PinArray(SubPins);
        ValueStr += PinHelpers::ExportTextPropDelimiter;
    }

    // 8. ParentPin引用
    if (ParentPin)
    {
        ValueStr += PinHelpers::ParentPinName + TEXT("=") + UEdGraphPin::ExportText_PinReference(ParentPin);
        ValueStr += PinHelpers::ExportTextPropDelimiter;
    }

    // ... 还有更多EditorOnly属性

    ValueStr += ")";
    return true;
}
```

### 4.2 PinType导出（反射遍历）

```cpp
// PinType结构体属性：
// - PinCategory (FName)
// - PinSubCategory (FName)
// - PinSubCategoryObject (TWeakObjectPtr<UObject>)
// - ContainerType (EPinContainerType)
// - PinValueType (FEdGraphPinType)
// - bIsReference (bool)
// - bIsWeakPointer (bool)
// - bIsConst (bool)
// - bIsUObjectWrapper (bool)
// - PinSubCategoryMemberReference (FMemberReference)
// - bSerializeAsSinglePrecisionFloat (bool)
```

**输出格式**：
```
PinType.PinCategory="exec",PinType.PinSubCategory="",PinType.PinSubCategoryObject=None,...
```

---

## 5. LinkedTo导出格式

### 5.1 ExportText_PinReference（EdGraphPin.cpp:2298-2307）

```cpp
FString UEdGraphPin::ExportText_PinReference(const UEdGraphPin* Pin)
{
    if (Pin)
    {
        const FString OwningNodeString = Pin->GetOwningNodeUnchecked() ? Pin->OwningNode->GetName() : TEXT("null");
        return OwningNodeString + " " + Pin->PinId.ToString();
    }
    return FString();
}
```

**格式**：`K2Node_CallFunction_1193 13FD260E4EE18FD0AA5F7085F9B509D6`

### 5.2 ExportText_PinArray

```cpp
FString UEdGraphPin::ExportText_PinArray(const TArray<UEdGraphPin*>& PinArray)
{
    FString RetVal;
    RetVal += "(";
    if (PinArray.Num() > 0)
    {
        for (UEdGraphPin* Pin : PinArray)
        {
            RetVal += ExportText_PinReference(Pin);
            RetVal += PinHelpers::ExportTextPropDelimiter;  // ','
        }
    }
    RetVal += ")";
    return RetVal;
}
```

**输出格式**：
```
LinkedTo=(K2Node_EnhancedInputAction_5 6412140B4E7EF6147A86BA8D2AFE9BA4,)
```

---

## 6. 完整Pin示例

UE编辑器导出的完整Pin格式：

```
CustomProperties Pin (PinId=13FD260E4EE18FD0AA5F7085F9B509D6,PinName="execute",PinType.PinCategory="exec",PinType.PinSubCategory="",PinType.PinSubCategoryObject=None,PinType.PinContainerType="None",PinType.bIsReference=False,PinType.bIsConst=False,PinType.bIsWeakPointer=False,PinType.bIsUObjectWrapper=False,LinkedTo=(K2Node_EnhancedInputAction_5 6412140B4E7EF6147A86BA8D2AFE9BA4,),PersistentGuid=00000000000000000000000000000000,bHidden=False,bNotConnectable=False,bDefaultValueIsReadOnly=False,bDefaultValueIsIgnored=False,bAdvancedView=False,bOrphanedPin=False,)
```

---

## 7. 解析实现指导

### 7.1 Pin解析器设计

```python
def parse_pin_text(pin_text: str) -> UEdGraphPin:
    """
    解析UE文本格式的Pin
    
    输入格式：
    CustomProperties Pin (PinId=XXX,PinName="execute",...)
    
    步骤：
    1. 前缀检测：确认是 "CustomProperties Pin "
    2. 提取括号内容：(...) → 字符串
    3. 属性解析：逗号分隔，键值对
    4. 特殊处理：
       - PinType.* 嵌套属性
       - LinkedTo 数组解析
       - PinId GUID解析
    """
```

### 7.2 关键解析点

| 属性 | 格式 | 解析方法 |
|------|------|----------|
| PinId | `PinId=13FD260E4EE18FD0AA5F7085F9B509D6` | 32字符16进制→16字节GUID |
| PinName | `PinName="execute"` | 字符串引号提取 |
| PinType.* | `PinType.PinCategory="exec"` | 嵌套属性名，点分隔 |
| LinkedTo | `LinkedTo=(NodeName GUID,NodeName2 GUID2,)` | 数组括号，节点名+空格+GUID |
| Direction | `Direction="EGPD_Output"` | 枚举字符串 |

### 7.3 GUID格式

**PinId**: 32字符16进制字符串 → 16字节（128位）
```python
def parse_guid(guid_str: str) -> bytes:
    """32字符16进制 → 16字节"""
    return bytes.fromhex(guid_str)
```

**示例**：
- `13FD260E4EE18FD0AA5F7085F9B509D6` → `0x13FD260E4EE18FD0AA5F7085F9B509D6` (16字节)

---

## 8. 与.uasset二进制的对应

### 8.1 Pin序列化（EdGraphPin.cpp:1838-1964）

```cpp
bool UEdGraphPin::Serialize(FArchive& Ar)
{
    Ar << OwningNode;   // UObject引用
    Ar << PinId;        // FGuid (16字节)
    Ar << PinName;      // FName
    Ar << PinToolTip;   // FString
    Ar << Direction;    // EEdGraphPinDirection (enum)
    PinType.Serialize(Ar);  // FEdGraphPinType结构体
    Ar << DefaultValue;     // FString
    Ar << AutogeneratedDefaultValue;  // FString
    Ar << DefaultObject;    // UObject引用
    Ar << DefaultTextValue; // FText
    
    // LinkedTo数组
    UEdGraphPin::SerializePinArray(Ar, LinkedTo, this, EPinResolveType::LinkedTo);
    
    // SubPins数组
    UEdGraphPin::SerializePinArray(Ar, SubPins, this, EPinResolveType::SubPins);
    
    // ParentPin引用
    SerializePin(Ar, ParentPin, ...);
    
    // ... EditorOnly属性
}
```

### 8.2 FEdGraphPinType序列化（EdGraphPin.cpp:163-346）

```cpp
bool FEdGraphPinType::Serialize(FArchive& Ar)
{
    Ar << PinCategory;           // FName
    Ar << PinSubCategory;        // FName
    Ar << PinSubCategoryObject;  // TWeakObjectPtr<UObject>
    Ar << ContainerType;         // EPinContainerType (enum)
    if (IsMap()) {
        Ar << PinValueType;      // FEdGraphPinType (嵌套)
    }
    Ar << bIsReference;          // bool
    Ar << bIsWeakPointer;        // bool
    Ar << PinSubCategoryMemberReference;  // FMemberReference
    Ar << bIsConst;              // bool
    Ar << bIsUObjectWrapper;     // bool
    Ar << bSerializeAsSinglePrecisionFloat;  // bool
    
    return true;
}
```

---

## 9. 结论

### 9.1 文本格式与二进制对应

| 文本属性 | 二进制字段 | 类型 |
|----------|-----------|------|
| PinId | `Ar << PinId` | FGuid (16字节) |
| PinName | `Ar << PinName` | FName |
| Direction | `Ar << Direction` | enum (uint8) |
| PinType.PinCategory | `Ar << PinCategory` | FName |
| PinType.PinSubCategory | `Ar << PinSubCategory` | FName |
| PinType.PinSubCategoryObject | `Ar << PinSubCategoryObject` | TObjectPtr |
| DefaultValue | `Ar << DefaultValue` | FString |
| LinkedTo | `SerializePinArray(Ar, LinkedTo, ...)` | TArray<UEdGraphPin*> |

### 9.2 v4.0实现路径

1. **Phase 18**: 修复属性解析阈值，添加Pin数组解析
2. **Phase 19**: 解析LinkedTo连接，构建执行流图
3. **Phase 20**: 解析节点位置、注释等辅助属性
4. **Phase 21**: 验证连接关系与执行流程

---

## 10. 参考文件清单

| 文件 | 行号 | 功能 |
|------|------|------|
| EdGraphUtilities.cpp | 458-481 | ExportNodesToText |
| EdGraphNode.cpp | 751-761 | ExportCustomProperties |
| EdGraphPin.cpp | 1077-1255 | ExportTextItem |
| EdGraphPin.cpp | 2298-2325 | ExportText_PinReference/Array |
| EdGraphPin.cpp | 163-346 | FEdGraphPinType::Serialize |
| EdGraphPin.cpp | 1838-1964 | UEdGraphPin::Serialize |

---

*研究完成：2026-05-04*
*源码版本：UE 5.7*