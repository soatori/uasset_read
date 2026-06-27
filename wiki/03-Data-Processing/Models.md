# Models

> Source: Development documentation `docs/dev-guide.html` → `section#models`

## Core Models

| Model | Description |
|-------|-------------|
| `UEdGraph` / `UEdGraphNode` / `UEdGraphPin` | Blueprint graph / node / pin |
| `FEdGraphPinType` / `FMemberReference` | Pin type / member reference |
| `PropertyTag` / `PropertyValue` | Property tag / property value base class |
| `StructValue` / `MapValue` / `SetValue` / `EnumValue` | Composite property values |
| `TextValue` / `DelegateValue` | Special property values |
| `ParseResult` / `StatusInfo` | Parse result / status |

## Blueprint Models

| Model | Description |
|-------|-------------|
| `BlueprintMetadata` | Blueprint metadata (variables, functions, events) |
| `BlueprintVariable` | Blueprint variable |
| `BlueprintFunction` | Blueprint function |
| `BlueprintEvent` | Blueprint event |
| `FunctionParameter` | Function parameter |

## Transformation Models

| Model | Description |
|-------|-------------|
| `VectorValue` | 3D vector (X, Y, Z) |
| `RotatorValue` | Rotation (Pitch, Yaw, Roll) |
| `ScaleValue` | Scale (X, Y, Z) |
