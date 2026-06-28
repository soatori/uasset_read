---
title: Blueprint Parsing
section: blueprint
---

# Blueprint Parsing

> **Module path**: `blueprint/`
> **Responsibility**: Extract blueprint variables, transforms, components, and metadata.

## Core API

### extract_blueprint_variables

<!-- data-api="extract_blueprint_variables" -->
```python
extract_blueprint_variables(properties: List[PropertyValue]) → List[BlueprintVariable]
```

Extracts blueprint variables from a list of properties.

### extract_blueprint_metadata

<!-- data-api="extract_blueprint_metadata" -->
```python
extract_blueprint_metadata(export, archive, import_map, export_map, name_map, summary, linker, graphs) → Tuple[BlueprintMetadata, str]
```

Extracts complete blueprint metadata, including variables, functions, events, and other information.

### parse_component_transform

<!-- data-api="parse_component_transform" -->
```python
parse_component_transform(properties: List[PropertyValue]) → Dict[str, Any]
```

Parses component transform data.

## Variable Extraction Paths

- **Primary path**: Parse FBPVariableDescription structures from `UBlueprint.NewVariables`
- **Fallback path**: Infer types and flags by iterating over properties

## Component-Related

### extract_components

<!-- data-api="extract_components" -->
```python
extract_components(export_map, import_map) → List[Dict]
```

Discovers SCS (SimpleConstructionScript) components from the ExportMap.

### extract_component_transforms

<!-- data-api="extract_component_transforms" -->
```python
extract_component_transforms(export_properties, component_name) → Dict
```

Extracts transform information for a component:
- `RelativeLocation` - Relative location
- `RelativeRotation` - Relative rotation
- `RelativeScale3D` - Relative scale

## Related Sections

- [[Graph]] - Graph Analysis
- [[Kismet]] - Kismet Decompilation
