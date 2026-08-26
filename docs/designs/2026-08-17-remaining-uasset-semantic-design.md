# Remaining UAsset Types — Semantic JSON Output Design

Date: 2026-08-17

Status: Implemented on `dev-0.5.5`

Issue: #557

## Quick Reference

### Asset Families Covered

| Family | Types | Domain | Key Content |
|--------|-------|--------|-------------|
| Mesh | StaticMesh, SkeletalMesh, Skeleton, LODSettings | structured | mesh_summary, materials, lod_info |
| Texture | Texture2D, TextureCube | resource | resource_properties, bulk_summary |
| Sound | SoundWave, SoundCue, SoundAttenuation | resource/graph | resource_properties, graph nodes |
| Data | CurveTable | structured | table_summary, columns |
| Niagara | System, Emitter, Script | graph | niagara_metadata, parameters |
| Anim | AnimSequence, AnimMontage, PoseAsset | structured | anim_summary, tracks, curves |
| User-defined | Enum, Struct | structured | enum_data/struct_data |
| Standalone | SubsurfaceProfile, CurveFloat, FoliageType | structured | profile/curve/foliage_properties |
| Movie | MovieScene, ControlRig | structured | scene_summary, tracks |

### Design Decisions Summary

| Decision | Choice |
|----------|--------|
| Mesh LOD screen sizes | Omit when unavailable (no fabrication) |
| SoundWave chunks | Summary only (per-chunk in debug) |
| Niagara types | Basic types only (float, int, vec3, etc.) |
| Anim compression | Read from properties, compute as fallback |
| User-defined metadata | Minimal (no GUID, export flags) |

### Delivery Status

All planned families are implemented and registered in the semantic pipeline:

1. **DataTable** — structured table exemplar
2. **Mesh** — structured domain
3. **Texture** — resource domain
4. **Sound** — graph/resource hybrid domain
5. **Anim** — structured domain with compression metadata
6. **Niagara** — graph domain
7. **Data (CurveTable)** — structured curve table domain
8. **User-defined** — enum and struct projection
9. **Standalone** — profile, curve, and foliage projection
10. **Movie** — MovieScene and ControlRig projection

### Additional Types (Opaque Stubs)

The following types are registered as opaque stubs with `partial_metadata` status. They provide basic type mapping without semantic content extraction:

| Category | Types | asset_type |
|----------|-------|------------|
| Physics | PhysicsAsset, PhysicalMaterial | `physics_asset`, `physical_material` |
| Animation | AnimLayerInterface | `anim_layer_interface` |
| Sound | SoundMix, SoundClass, SoundSubmix | `sound_mix`, `sound_class`, `sound_submix` |
| AI | BehaviorTree, BlackboardData | `behavior_tree`, `blackboard_data` |
| Data | DataAsset, PrimaryDataAsset | `data_asset`, `primary_data_asset` |
| Landscape | Landscape, LandscapeGrassType, LandscapeLayerInfoObject | `landscape`, `landscape_grass_type`, `landscape_layer_info` |
| World | World, Level | `world`, `level` |
| Particles | ParticleSystem | `particle_system` |
| UI | WidgetBlueprintGeneratedClass, WidgetBlueprint | `widget_blueprint` |
| Texture | Texture2DArray, VolumeTexture | `texture` |
| Media | MediaPlayer, MediaTexture, MediaSource | `media_player`, `media_texture`, `media_source` |
| Cloth/Hair | ClothAsset, GroomAsset | `cloth_asset`, `groom_asset` |
| Sparse VT | SparseVolumeTexture | `sparse_volume_texture` |

---

## 1. Goal

Define the semantic content model for all remaining non-Blueprint UAsset types not covered by dedicated issues (#554–#556). This design extends the common `asset_semantic` envelope with domain-specific content for 9 asset families.

## 2. Scope

This design covers:

- Per-family content model definitions (structured, resource, graph, hybrid)
- Field specifications with types, descriptions, and value domains
- Reference table usage patterns
- Coverage scopes and diagnostic codes
- Size/loss limits ($bounded wrapper usage)
- Example JSON output for representative assets

This design does NOT cover:

- Implementation details (covered by per-family sub-issues)
- Blueprint types (#554, #555)
- Material graph domain (#556)
- DataTable (in progress as exemplar)
- Additional types registered as opaque stubs (see "Additional Types" section)

## 3. Asset Family Classification

| # | Family | asset_type values | Domain | Parse Machinery |
|---|--------|-------------------|--------|-----------------|
| 1 | Mesh | `static_mesh`, `skeletal_mesh`, `skeleton`, `skeletal_mesh_lod_settings` | structured | PropertyMetadataHandler + parse_skeleton |
| 2 | Texture | `texture` | resource | PropertyMetadataHandler |
| 3 | Sound | `sound_wave`, `sound_cue`, `sound_attenuation` | resource/graph | PropertyMetadataHandler + parse_sound_wave |
| 4 | Data (tables) | `curve_table` | structured | parse_curve_table |
| 5 | Niagara | `niagara_system`, `niagara_emitter`, `niagara_script` | graph | Niagara handlers |
| 6 | Anim (non-BP) | `anim_sequence`, `anim_montage`, `pose_asset`, `anim_curve_compression_settings` | structured | AnimSequenceHandler, AnimMontageHandler |
| 7 | User-defined | `enum`, `struct` | structured | generic property projection |
| 8 | Standalone | `subsurface_profile`, `curve`, `foliage_type` | structured/resource | parse_subsurface_profile, parse_foliage_type |
| 9 | Movie | `movie_scene`, `movie_scene_control_rig_*` | structured | MovieSceneHandler |

## 4. Family 1: Mesh

### 4.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `static_mesh` | StaticMesh | LODs, sections, materials, bounds, lightmap settings |
| `skeletal_mesh` | SkeletalMesh | LODs, sections, materials, ref skeleton, physics assets |
| `skeleton` | Skeleton | Bone hierarchy, retarget sources, sockets, slot groups |
| `skeletal_mesh_lod_settings` | SkeletalMeshLODSettings | LOD quality thresholds, screen sizes |

### 4.2 Content Model — StaticMesh

```json
{
  "mesh_summary": {
    "lod_count": 3,
    "section_count": 5,
    "vertex_count": 12000,
    "triangle_count": 8000,
    "material_count": 4,
    "bounds": {
      "origin": {"x": 0.0, "y": 0.0, "z": 50.0},
      "extent": {"x": 100.0, "y": 100.0, "z": 50.0}
    },
    "lightmap_resolution": 256,
    "lightmap_coordinate_index": 1,
    "lod_group": "LargeWorld"
  },
  "materials": [
    {
      "slot_index": 0,
      "material_ref": 0,
      "material_name": "M_Wood"
    }
  ],
  "lod_info": [
    {
      "lod_index": 0,
      "screen_size": 1.0,
      "vertex_count": 5000,
      "triangle_count": 3000,
      "section_count": 2
    }
  ],
  "asset_type_data": {}
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mesh_summary` | object | yes | Business-level mesh statistics |
| `mesh_summary.lod_count` | int | yes | Number of LOD levels |
| `mesh_summary.section_count` | int | yes | Total sections across all LODs |
| `mesh_summary.vertex_count` | int | yes | Total vertices (all LODs) |
| `mesh_summary.triangle_count` | int | yes | Total triangles (all LODs) |
| `mesh_summary.material_count` | int | yes | Unique material slots |
| `mesh_summary.bounds` | object | yes | Axis-aligned bounding box |
| `mesh_summary.lightmap_resolution` | int | no | Lightmap texture resolution |
| `mesh_summary.lightmap_coordinate_index` | int | no | UV channel for lightmaps |
| `mesh_summary.lod_group` | string | no | LOD group name |
| `materials` | array | yes | Material slot assignments |
| `materials[].slot_index` | int | yes | Material slot index |
| `materials[].material_ref` | int | yes | Index into envelope `references` |
| `materials[].material_name` | string | yes | Material object name |
| `lod_info` | array | yes | Per-LOD summary statistics |
| `lod_info[].lod_index` | int | yes | LOD level index |
| `lod_info[].screen_size` | float | no | Screen size threshold (omitted when unavailable — see §18.1) |
| `lod_info[].vertex_count` | int | yes | Vertex count for this LOD |
| `lod_info[].triangle_count` | int | yes | Triangle count for this LOD |
| `lod_info[].section_count` | int | yes | Section count for this LOD |
| `asset_type_data` | object | yes | Compatibility passthrough |

**Coverage Scopes:**

| Scope | Condition | Description |
|-------|-----------|-------------|
| `mesh_summary` | always | Business-level statistics |
| `materials` | always | Material slot assignments |
| `lod_info` | always | Per-LOD statistics |
| `asset_type_data` | if present | Raw property passthrough |

**Diagnostic Codes:**

| Code | Severity | Description |
|------|----------|-------------|
| `MESH_TRUNCATED_LOD` | warning | LOD data truncated by safety limit |
| `MESH_MISSING_BOUNDS` | info | Bounds data not available |
| `MESH_INVALID_MATERIAL_REF` | error | Material reference index out of range |

### 4.3 Content Model — SkeletalMesh

```json
{
  "mesh_summary": {
    "lod_count": 2,
    "section_count": 4,
    "vertex_count": 15000,
    "triangle_count": 10000,
    "material_count": 3,
    "bone_count": 65,
    "has_skeleton": true,
    "has_physics_asset": true,
    "bounds": {
      "origin": {"x": 0.0, "y": 0.0, "z": 90.0},
      "extent": {"x": 50.0, "y": 50.0, "z": 90.0}
    }
  },
  "materials": [
    {
      "slot_index": 0,
      "material_ref": 1,
      "material_name": "M_Body"
    }
  ],
  "lod_info": [
    {
      "lod_index": 0,
      "vertex_count": 8000,
      "triangle_count": 5000,
      "section_count": 2
    }
  ],
  "skeleton_ref": 2,
  "physics_asset_ref": 3,
  "asset_type_data": {}
}
```

**Additional Fields (beyond StaticMesh):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mesh_summary.bone_count` | int | yes | Number of bones |
| `mesh_summary.has_skeleton` | bool | yes | Skeleton reference present |
| `mesh_summary.has_physics_asset` | bool | yes | Physics asset reference present |
| `skeleton_ref` | int | no | Index into envelope `references` for skeleton |
| `physics_asset_ref` | int | no | Index into envelope `references` for physics asset |

### 4.4 Content Model — Skeleton

```json
{
  "skeleton_data": {
    "bone_count": 65,
    "root_bone": "root",
    "bones": [
      {
        "index": 0,
        "name": "root",
        "parent_index": -1
      },
      {
        "index": 1,
        "name": "pelvis",
        "parent_index": 0
      }
    ],
    "retarget_source_count": 2,
    "retarget_sources": [
      {
        "name": "default",
        "pose_name": "default",
        "transform_count": 65,
        "source_mesh_ref": null
      }
    ],
    "socket_count": 10,
    "slot_group_count": 2
  },
  "asset_type_data": {}
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `skeleton_data` | object | yes | Skeleton-specific data |
| `skeleton_data.bone_count` | int | yes | Total bone count |
| `skeleton_data.root_bone` | string | yes | Root bone name |
| `skeleton_data.bones` | array | yes | Bone hierarchy (truncated to preview) |
| `skeleton_data.bones[].index` | int | yes | Bone index |
| `skeleton_data.bones[].name` | string | yes | Bone name |
| `skeleton_data.bones[].parent_index` | int | yes | Parent bone index (-1 for root) |
| `skeleton_data.retarget_source_count` | int | yes | Number of retarget sources |
| `skeleton_data.retarget_sources` | array | yes | Retarget source definitions |
| `skeleton_data.socket_count` | int | yes | Number of sockets |
| `skeleton_data.slot_group_count` | int | yes | Number of slot groups |

**Size Limits:**

- `skeleton_data.bones` uses `$bounded` when count exceeds 1000 (preview first 100)
- Full bone list available in debug mode only

**Diagnostic Codes:**

| Code | Severity | Description |
|------|----------|-------------|
| `SKELETON_BONE_LIMIT` | warning | Bone count exceeds safety limit |
| `SKELETON_INVALID_HIERARCHY` | error | Bone hierarchy has cycles or invalid parents |

### 4.5 Content Model — SkeletalMeshLODSettings

```json
{
  "lod_settings": {
    "quality_thresholds": [
      {
        "lod_index": 0,
        "screen_size": 1.0,
        "allowed_error": 0.0
      },
      {
        "lod_index": 1,
        "screen_size": 0.5,
        "allowed_error": 0.1
      }
    ],
    "lod_group": "Character",
    "force_morph": false
  },
  "asset_type_data": {}
}
```

## 5. Family 2: Texture

### 5.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `texture` | Texture2D, TextureCube | Format, dimensions, mip chain, streaming info |

### 5.2 Content Model — Texture2D

```json
{
  "resource_properties": {
    "size_x": 1024,
    "size_y": 1024,
    "format": "PF_DXT5",
    "num_mips": 10,
    "is_streaming": true,
    "streaming_channels": 1,
    "lod_group": "TEXTUREGROUP_World",
    "address_x": "TA_Wrap",
    "address_y": "TA_Wrap",
    "filter": "TF_Bilinear",
    "srgb": true
  },
  "bulk_summary": {
    "total_mip_bytes": 1048576,
    "compressed_mip_bytes": 524288,
    "chunk_count": 1,
    "first_mip": 0
  },
  "asset_type_data": {}
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resource_properties` | object | yes | Texture metadata |
| `resource_properties.size_x` | int | yes | Width in pixels |
| `resource_properties.size_y` | int | yes | Height in pixels |
| `resource_properties.format` | string | yes | Pixel format (e.g., PF_DXT5) |
| `resource_properties.num_mips` | int | yes | Number of mip levels |
| `resource_properties.is_streaming` | bool | yes | Texture streaming enabled |
| `resource_properties.streaming_channels` | int | no | Streaming channels count |
| `resource_properties.lod_group` | string | no | Texture LOD group |
| `resource_properties.address_x` | string | no | X addressing mode |
| `resource_properties.address_y` | string | no | Y addressing mode |
| `resource_properties.filter` | string | no | Texture filter mode |
| `resource_properties.srgb` | bool | no | sRGB color space flag |
| `bulk_summary` | object | yes | Bulk data summary |
| `bulk_summary.total_mip_bytes` | int | yes | Total uncompressed mip bytes |
| `bulk_summary.compressed_mip_bytes` | int | no | Total compressed mip bytes |
| `bulk_summary.chunk_count` | int | yes | Number of streaming chunks |
| `bulk_summary.first_mip` | int | no | First mip level in package |

**Coverage Scopes:**

| Scope | Condition | Description |
|-------|-----------|-------------|
| `resource_properties` | always | Texture metadata |
| `bulk_summary` | always | Bulk data summary |
| `asset_type_data` | if present | Raw property passthrough |

**Diagnostic Codes:**

| Code | Severity | Description |
|------|----------|-------------|
| `TEXTURE_OPAQUE_FORMAT` | info | Pixel format not parsed (opaque bulk data) |
| `TEXTURE_MISSING_DIMENSIONS` | warning | SizeX/SizeY not available |

### 5.3 Content Model — TextureCube

Same as Texture2D with additional field:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resource_properties.cube_face_count` | int | yes | Number of cube faces (always 6) |

## 6. Family 3: Sound

### 6.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `sound_wave` | SoundWave | Format, duration, channels, compression |
| `sound_cue` | SoundCue | Graph nodes, mixer configuration |
| `sound_attenuation` | SoundAttenuation | Attenuation settings, spatialization |

### 6.2 Content Model — SoundWave

**Design Note:** `bulk_summary` contains summary only — per-chunk sizes available in debug mode (see §18.2).

```json
{
  "resource_properties": {
    "duration": 3.5,
    "sample_rate": 44100,
    "channel_count": 2,
    "format": "OGG",
    "compression_quality": 0.8,
    "sound_group": "SOUNDGROUP_UI",
    "loading_behavior": "Default"
  },
  "bulk_summary": {
    "total_pcm_bytes": 617400,
    "compressed_bytes": 123480,
    "chunk_count": 1,
    "is_streaming": false
  },
  "asset_type_data": {}
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resource_properties` | object | yes | Sound wave metadata |
| `resource_properties.duration` | float | yes | Duration in seconds |
| `resource_properties.sample_rate` | int | yes | Sample rate (Hz) |
| `resource_properties.channel_count` | int | yes | Number of channels |
| `resource_properties.format` | string | yes | Audio format (OGG, PCM, etc.) |
| `resource_properties.compression_quality` | float | no | Compression quality (0.0-1.0) |
| `resource_properties.sound_group` | string | no | Sound group classification |
| `resource_properties.loading_behavior` | string | no | Loading behavior enum |
| `bulk_summary` | object | yes | Bulk data summary |
| `bulk_summary.total_pcm_bytes` | int | yes | Total uncompressed PCM bytes |
| `bulk_summary.compressed_bytes` | int | yes | Total compressed bytes |
| `bulk_summary.chunk_count` | int | yes | Number of streaming chunks |
| `bulk_summary.is_streaming` | bool | yes | Streaming enabled |

**Diagnostic Codes:**

| Code | Severity | Description |
|------|----------|-------------|
| `SOUND_OPAQUE_DATA` | info | Audio data not parsed (opaque bulk) |
| `SOUND_MISSING_DURATION` | warning | Duration not available |

### 6.3 Content Model — SoundCue

```json
{
  "graph_metadata": {
    "class_name": "SoundCue",
    "object_name": "SC_Wind",
    "node_count": 5,
    "mixer_node_count": 1,
    "wave_player_count": 3
  },
  "nodes": [
    {
      "id": "n0",
      "kind": "wave_player",
      "label": "SoundWavePlayer",
      "outputs": {
        "output": {"type": "audio"}
      },
      "refs": [{"target": 0, "role": "sound_wave"}]
    },
    {
      "id": "n1",
      "kind": "mixer",
      "label": "SoundCueMixer",
      "inputs": {
        "input_0": {"type": "audio"},
        "input_1": {"type": "audio"}
      },
      "outputs": {
        "output": {"type": "audio"}
      }
    }
  ],
  "edges": [
    {
      "from": {"node": "n0", "pin": "output"},
      "to": {"node": "n1", "pin": "input_0"}
    }
  ],
  "asset_type_data": {}
}
```

**Design Notes:**

- SoundCue uses the graph domain pattern (nodes + edges)
- Wave player nodes reference SoundWave assets via `refs`
- Mixer nodes combine audio streams
- Edge semantics: audio signal flow

### 6.4 Content Model — SoundAttenuation

```json
{
  "attenuation_properties": {
    "attenuation_shape": "Sphere",
    "attenuation_radius": 3600.0,
    "falloff_function": "Linear",
    "spatialization_algorithm": "Panning",
    "battenuate_over_distance": true,
    "battenuate_over_time": true,
    "distance_algorithm": "Linear",
    "attenuation_shape_extents": {
      "x": 100.0,
      "y": 100.0,
      "z": 100.0
    }
  },
  "asset_type_data": {}
}
```

## 7. Family 4: Data (Tables)

### 7.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `curve_table` | CurveTable | Curve rows, column definitions |

### 7.2 Content Model — CurveTable

```json
{
  "table_summary": {
    "row_count": 50,
    "column_count": 3,
    "curve_type": "CurveFloat"
  },
  "columns": [
    {
      "name": "Damage",
      "curve_type": "CurveFloat"
    },
    {
      "name": "Radius",
      "curve_type": "CurveFloat"
    }
  ],
  "row_names": [
    "SmallExplosion",
    "LargeExplosion"
  ],
  "asset_type_data": {}
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `table_summary` | object | yes | Table metadata |
| `table_summary.row_count` | int | yes | Number of rows |
| `table_summary.column_count` | int | yes | Number of columns |
| `table_summary.curve_type` | string | yes | Curve type (CurveFloat, CurveVector, etc.) |
| `columns` | array | yes | Column definitions |
| `columns[].name` | string | yes | Column name |
| `columns[].curve_type` | string | yes | Curve type for this column |
| `row_names` | array | yes | Row name list (truncated with $bounded if large) |

**Size Limits:**

- `row_names` uses `$bounded` when count exceeds 1000 (preview first 100)

## 8. Family 5: Niagara

### 8.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `niagara_system` | NiagaraSystem | Emitter references, system properties |
| `niagara_emitter` | NiagaraEmitter | Scripts, parameters, sim stage |
| `niagara_script` | NiagaraScript | Script parameters, bytecode summary |

### 8.2 Content Model — NiagaraSystem

```json
{
  "niagara_metadata": {
    "emitter_count": 3,
    "total_spawn_rate": 1000,
    "has_gpu_computation": true
  },
  "emitters": [
    {
      "index": 0,
      "name": "SmokeEmitter",
      "emitter_ref": 0,
      "enabled": true,
      "spawn_rate": 500
    }
  ],
  "asset_type_data": {}
}
```

### 8.3 Content Model — NiagaraEmitter

**Design Note:** Parameter types use basic strings only: `float`, `int`, `vec3`, `bool`, etc. (see §18.3).

```json
{
  "niagara_metadata": {
    "script_count": 2,
    "parameter_count": 15,
    "sim_stage_count": 1,
    "has_gpu_computation": false
  },
  "scripts": [
    {
      "index": 0,
      "name": "EmitterUpdate",
      "script_ref": 0,
      "stage": "EmitterUpdate"
    },
    {
      "index": 1,
      "name": "ParticleUpdate",
      "script_ref": 1,
      "stage": "ParticleUpdate"
    }
  ],
  "parameters": {
    "uniform": [
      {
        "name": "SpawnRate",
        "type": "float"
      }
    ],
    "input": [],
    "output": []
  },
  "asset_type_data": {}
}
```

### 8.4 Content Model — NiagaraScript

```json
{
  "niagara_metadata": {
    "script_type": "Module",
    "parameter_count": 8,
    "has_bytecode": true,
    "bytecode_size": 2048
  },
  "parameters": {
    "input": [
      {
        "name": "DeltaTime",
        "type": "float"
      }
    ],
    "output": [
      {
        "name": "Position",
        "type": "vec3"
      }
    ],
    "uniform": []
  },
  "asset_type_data": {}
}
```

**Design Notes:**

- Niagara uses graph-like patterns but with distinct semantics (particle simulation)
- Scripts represent compute stages (EmitterUpdate, ParticleUpdate, etc.)
- Parameters are typed (float, int, vec3, etc.)
- Bytecode size provided for complexity assessment

## 9. Family 6: Animation (non-BP)

### 9.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `anim_sequence` | AnimSequence | Keyframes, tracks, compression |
| `anim_montage` | AnimMontage | Sections, slots, branching points |
| `pose_asset` | PoseAsset | Pose names, blend weights |
| `anim_curve_compression_settings` | AnimCurveCompressionSettings | Compression codec config |

### 9.2 Content Model — AnimSequence

```json
{
  "anim_summary": {
    "frame_count": 120,
    "frame_rate": 30.0,
    "duration": 4.0,
    "bone_track_count": 65,
    "curve_count": 5,
    "motion_extractor_count": 3,
    "has_additive_animation": false,
    "has_root_motion": true
  },
  "tracks": {
    "translation": {
      "track_count": 65,
      "key_count_total": 7800
    },
    "rotation": {
      "track_count": 65,
      "key_count_total": 7800
    },
    "scale": {
      "track_count": 0,
      "key_count_total": 0
    }
  },
  "curves": [
    {
      "name": "EyeBlinkLeft",
      "type": "material",
      "key_count": 120
    }
  ],
  "compression": {
    "codec": "UniformQuantization",
    "compressed_size": 50000,
    "original_size": 150000,
    "compression_ratio": 0.33
  },
  "asset_type_data": {}
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anim_summary` | object | yes | Animation metadata |
| `anim_summary.frame_count` | int | yes | Total frames |
| `anim_summary.frame_rate` | float | yes | Frames per second |
| `anim_summary.duration` | float | yes | Duration in seconds |
| `anim_summary.bone_track_count` | int | yes | Number of bone tracks |
| `anim_summary.curve_count` | int | yes | Number of animation curves |
| `anim_summary.motion_extractor_count` | int | yes | Motion extraction tracks |
| `anim_summary.has_additive_animation` | bool | yes | Additive animation flag |
| `anim_summary.has_root_motion` | bool | yes | Root motion flag |
| `tracks` | object | yes | Track statistics by type |
| `tracks.translation` | object | yes | Translation track stats |
| `tracks.rotation` | object | yes | Rotation track stats |
| `tracks.scale` | object | yes | Scale track stats |
| `curves` | array | yes | Animation curve definitions |
| `compression` | object | no | Compression information (see §18.4 for read/compute decision) |
| `compression.codec` | string | yes | Compression codec name (read from properties) |
| `compression.compressed_size` | int | yes | Compressed data size |
| `compression.original_size` | int | yes | Original data size |
| `compression.compression_ratio` | float | no | Compression ratio (read from properties, compute as fallback) |

**Size Limits:**

- Individual keyframe data never included in standard output
- Track statistics provide summary only

### 9.3 Content Model — AnimMontage

```json
{
  "montage_summary": {
    "slot_count": 2,
    "section_count": 4,
    "branching_point_count": 2,
    "blend_in_time": 0.2,
    "blend_out_time": 0.2,
    "duration": 5.0
  },
  "slots": [
    {
      "name": "UpperBody",
      "track_index": 0
    }
  ],
  "sections": [
    {
      "name": "Default",
      "start_time": 0.0,
      "end_time": 2.5,
      "next_section": "Attack"
    }
  ],
  "branching_points": [
    {
      "time": 1.5,
      "notify_name": "FootStep"
    }
  ],
  "asset_type_data": {}
}
```

### 9.4 Content Model — PoseAsset

```json
{
  "pose_summary": {
    "pose_count": 10,
    "blend_pose_count": 5,
    "has_scale": false
  },
  "poses": [
    {
      "name": "Idle",
      "index": 0
    },
    {
      "name": "Run",
      "index": 1
    }
  ],
  "asset_type_data": {}
}
```

### 9.5 Content Model — AnimCurveCompressionSettings

```json
{
  "compression_settings": {
    "codec_class": "AnimCurveCompressionCodec_Uniform",
    "max_curve_count": 256,
    "error_threshold": 0.01
  },
  "asset_type_data": {}
}
```

## 10. Family 7: User-Defined Types

### 10.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `enum` | UserDefinedEnum | Enum names, display names, values |
| `struct` | UserDefinedStruct | Struct properties, metadata |

### 10.2 Content Model — UserDefinedEnum

```json
{
  "enum_data": {
    "enum_name": "EMyStatus",
    "display_name": "My Status",
    "entry_count": 4,
    "entries": [
      {
        "name": "Active",
        "display_name": "Active",
        "value": 0
      },
      {
        "name": "Inactive",
        "display_name": "Inactive",
        "value": 1
      }
    ]
  },
  "asset_type_data": {}
}
```

### 10.3 Content Model — UserDefinedStruct

**Design Note:** Properties contain only `name`, `type`, `display_name` — no GUID, export flags, or metadata (see §18.5).

```json
{
  "struct_data": {
    "struct_name": "FMyStruct",
    "display_name": "My Struct",
    "property_count": 5,
    "properties": [
      {
        "name": "Health",
        "type": "float",
        "display_name": "Health"
      },
      {
        "name": "Name",
        "type": "string",
        "display_name": "Name"
      }
    ]
  },
  "asset_type_data": {}
}
```

## 11. Family 8: Standalone

### 11.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `subsurface_profile` | SubsurfaceProfile | Subsurface scattering settings |
| `curve` | CurveFloat | Float curve keys |
| `foliage_type` | FoliageType_InstancedStaticMesh | Foliage instance settings |

### 11.2 Content Model — SubsurfaceProfile

```json
{
  "profile_properties": {
    "surface_albedo": {"r": 0.9, "g": 0.7, "b": 0.6},
    "mean_free_path": 1.0,
    "mean_free_path_dist": 1.0,
    "subsurface_color": {"r": 1.0, "g": 0.8, "b": 0.7},
    "boundary_color_bleed": {"r": 1.0, "g": 1.0, "b": 1.0},
    "extinction_scale": 1.0,
    "normal_scale": 1.0,
    "custom_profile_curve": null
  },
  "asset_type_data": {}
}
```

### 11.3 Content Model — CurveFloat

```json
{
  "curve_data": {
    "key_count": 5,
    "pre_infinity_extrap": "Cycle",
    "post_infinity_extrap": "Cycle",
    "keys": [
      {
        "time": 0.0,
        "value": 0.0,
        "interpolation": "Auto"
      },
      {
        "time": 1.0,
        "value": 1.0,
        "interpolation": "Auto"
      }
    ]
  },
  "asset_type_data": {}
}
```

**Size Limits:**

- `curve_data.keys` uses `$bounded` when count exceeds 100 (preview first 20)

### 11.4 Content Model — FoliageType

```json
{
  "foliage_properties": {
    "mesh_ref": 0,
    "material_refs": [1],
    "density": 1.0,
    "scaling": "Uniform",
    "scale_min": 0.8,
    "scale_max": 1.2,
    "collision_radius": 50.0,
    "height_range_min": 100.0,
    "height_range_max": 200.0
  },
  "asset_type_data": {}
}
```

## 12. Family 9: Movie

### 12.1 Applicable Types

| asset_type | UE Class | Primary Content |
|------------|----------|-----------------|
| `movie_scene` | MovieScene | Sections, tracks, frames |
| `movie_scene_control_rig_*` | MovieSceneControlRig* | Control rig binding |

### 12.2 Content Model — MovieScene

```json
{
  "scene_summary": {
    "track_count": 3,
    "section_count": 5,
    "frame_rate": 30.0,
    "start_frame": 0,
    "end_frame": 300,
    "duration_seconds": 10.0
  },
  "tracks": [
    {
      "name": "CameraCut",
      "type": "MovieSceneCameraCutTrack",
      "section_count": 2
    }
  ],
  "asset_type_data": {}
}
```

## 13. Common Patterns

### 13.1 Summary Object Pattern

All families use a `*_summary` or `*_properties` object for business-level fields:

| Family | Summary Key | Purpose |
|--------|-------------|---------|
| Mesh | `mesh_summary` | Vertex/triangle counts, bounds, LOD info |
| Texture | `resource_properties` | Dimensions, format, streaming |
| Sound | `resource_properties` | Duration, sample rate, channels |
| Data | `table_summary` | Row/column counts |
| Niagara | `niagara_metadata` | Emitter/script counts |
| Anim | `anim_summary` | Frame count, duration, track counts |
| User-defined | `enum_data` / `struct_data` | Type-specific metadata |
| Standalone | `*_properties` | Varies by type |
| Movie | `scene_summary` | Track/section counts, frame range |

### 13.2 Reference Pattern

All families use reference table indices for cross-asset references:

```json
"materials": [
  {"slot_index": 0, "material_ref": 0}  // Index into envelope references
]
```

### 13.3 Bounded Wrapper Pattern

Large arrays use `$bounded` wrapper:

```json
{
  "$bounded": {
    "type": "array",
    "count": 5000,
    "original_bytes": 200000,
    "sha256": "abc123...",
    "preview": [...]
  }
}
```

### 13.4 asset_type_data Passthrough

All families include `asset_type_data` for backward compatibility:

```json
"asset_type_data": {
  // Raw property passthrough from parser
}
```

## 14. Coverage and Diagnostics

### 14.1 Coverage Scopes by Family

| Family | Scope Names |
|--------|-------------|
| Mesh | `mesh_summary`, `materials`, `lod_info`, `skeleton_data` (Skeleton only) |
| Texture | `resource_properties`, `bulk_summary` |
| Sound | `resource_properties`, `bulk_summary` (SoundWave), `graph_data` (SoundCue) |
| Data | `table_summary`, `columns`, `row_names` |
| Niagara | `niagara_metadata`, `emitters`/`scripts`, `parameters` |
| Anim | `anim_summary`, `tracks`, `curves`, `compression` |
| User-defined | `enum_data`/`struct_data` |
| Standalone | `profile_properties`/`curve_data`/`foliage_properties` |
| Movie | `scene_summary`, `tracks` |

### 14.2 Diagnostic Code Prefixes

| Prefix | Family | Examples |
|--------|--------|----------|
| `MESH_*` | Mesh | `MESH_TRUNCATED_LOD`, `MESH_MISSING_BOUNDS` |
| `TEXTURE_*` | Texture | `TEXTURE_OPAQUE_FORMAT`, `TEXTURE_MISSING_DIMENSIONS` |
| `SOUND_*` | Sound | `SOUND_OPAQUE_DATA`, `SOUND_MISSING_DURATION` |
| `TABLE_*` | Data | `TABLE_TRUNCATED_ROWS`, `TABLE_MISSING_SCHEMA` |
| `NIAGARA_*` | Niagara | `NIAGARA_SCRIPT_OPAQUE`, `NIAGARA_MISSING_PARAMS` |
| `ANIM_*` | Anim | `ANIM_TRUNCATED_KEYS`, `ANIM_MISSING_TRACKS` |
| `USER_*` | User-defined | `USER_MISSING_ENTRIES`, `USER_MISSING_PROPERTIES` |
| `SCENE_*` | Movie | `SCENE_TRUNCATED_TRACKS` |

## 15. Test Fixtures

### 15.1 Real Asset Fixtures

| Family | Fixture Asset | Source | asset_type |
|--------|--------------|--------|------------|
| Mesh | `SM_Chair.uasset` | StarterContent | `static_mesh` |
| Mesh | `SK_Mannequin.uasset` | Mannequin | `skeletal_mesh` |
| Mesh | `SK_Mannequin_Skeleton.uasset` | Mannequin | `skeleton` |
| Texture | `T_Wood_D.uasset` | StarterContent | `texture` |
| Sound | `Starter_Background_Cue.uasset` | StarterContent | `sound_cue` |
| Data | `DT_Config.uasset` | Custom | `data_table` |
| Anim | `Idle_to_Run.uasset` | Mannequin | `anim_sequence` |

### 15.2 Acceptance Assertions

Each fixture must:

1. Pass `validate_semantic_document()` with zero errors
2. Have `status.parse` != `failed`
3. Contain expected summary fields
4. Use valid reference indices
5. Not exceed size limits without `$bounded` wrapper

## 16. Implementation Boundaries

### 16.1 Per-Family Sub-Issues

| Family | Sub-Issue | Branch | Scope |
|--------|-----------|--------|-------|
| Mesh | #557a | `feature/mesh-semantic` | StaticMesh, SkeletalMesh, Skeleton, LODSettings |
| Texture | #557b | `feature/texture-semantic` | Texture2D, TextureCube |
| Sound | #557c | `feature/sound-semantic` | SoundWave, SoundCue, SoundAttenuation |
| Data | #557d | `feature/datatable-semantic` | CurveTable (DataTable in progress) |
| Niagara | #557e | `feature/niagara-semantic` | NiagaraSystem, NiagaraEmitter, NiagaraScript |
| Anim | #557f | `feature/anim-semantic` | AnimSequence, AnimMontage, PoseAsset, CompressionSettings |
| User-defined | #557g | `feature/userdef-semantic` | UserDefinedEnum, UserDefinedStruct |
| Standalone | #557h | `feature/standalone-semantic` | SubsurfaceProfile, CurveFloat, FoliageType |
| Movie | #557i | `feature/movie-semantic` | MovieScene, MovieSceneControlRig* |

### 16.2 Implementation Order

1. **DataTable** (exemplar, in progress)
2. **Mesh** — most complex, validates structured domain pattern
3. **Texture** — validates resource domain pattern
4. **Sound** — validates graph + resource hybrid pattern
5. **Anim** — validates structured domain with compression
6. **Niagara** — validates graph domain pattern
7. **Data (CurveTable)** — sibling to DataTable
8. **User-defined** — simple property projection
9. **Standalone** — minimal, can be batched
10. **Movie** — minimal, can be batched

## 17. Constraints

- **Zero runtime dependencies** — no third-party packages
- **Read-only** — parse only; no modification or writing
- **Unbaked/editor-saved assets only** — cooked assets have data stripped
- **Standard output never enumerates** vertices, indices, weights, pixels, or samples
- **Unknown/unsupported classes** must report `opaque` or limited coverage
- **Deterministic output** — same input produces byte-identical output
- **$bounded for large arrays** — always with sha256 for cross-version consistency
- **Reference table indices only** — no inline package paths in domain content

## 18. Design Decisions

### 18.1 Mesh LOD Screen Sizes

**Decision:** Omit `lod_info[].screen_size` when not available from properties. Do not fabricate values.

**Rationale:** Screen size thresholds are editor-only data that may not be present in all assets. Fabricating values would produce misleading output. The field is optional and should be omitted when unavailable.

**Impact:**
- `lod_info[].screen_size` is marked as optional in field descriptions
- Coverage scope does not require this field
- No diagnostic code needed (natural absence)

### 18.2 SoundWave Streaming Chunks

**Decision:** `bulk_summary` includes only summary statistics (total bytes, chunk count). Per-chunk sizes available in debug mode only.

**Rationale:** Standard output should provide bounded summaries without enumerating chunk details. Per-chunk data is useful for debugging streaming issues but not for typical semantic analysis.

**Impact:**
- `bulk_summary` structure remains simple: `total_pcm_bytes`, `compressed_bytes`, `chunk_count`, `is_streaming`
- Debug mode may include `chunks` array with per-chunk sizes
- No $bounded needed for normal chunk counts

### 18.3 Niagara Parameter Types

**Decision:** Use basic type strings only: `float`, `int`, `vec2`, `vec3`, `vec4`, `bool`, `string`, `enum`, `struct`, `array`, `texture`, `curve`, `simulation`.

**Rationale:** Detailed type information (e.g., specific struct layouts) would require parsing Niagara script bytecode, which is complex and version-dependent. Basic types provide sufficient semantic information for most use cases.

**Impact:**
- `parameters[].type` uses simple string identifiers
- No nested type definitions in standard output
- Complex types (struct, array) may include `element_type` for simple cases

### 18.4 Animation Curve Compression

**Decision:** Read compression ratio from properties when available. Compute as fallback when properties are missing.

**Rationale:** UE stores compression metadata in `AnimCurveCompressionCodec` properties. Reading directly ensures accuracy. Computing from raw sizes provides fallback when metadata is unavailable.

**Impact:**
- `compression.ratio` is optional (omitted when both source and metadata unavailable)
- `compression.codec` read from `CodecClass` property
- Fallback computation: `compressed_size / original_size` when both sizes available

### 18.5 User-Defined Struct Properties

**Decision:** Do NOT include property metadata (GUID, export flags, replication info). Keep semantic output minimal.

**Rationale:** GUIDs and export flags are implementation details not relevant for semantic analysis. Including them would add noise without value for typical use cases (code generation, documentation, analysis).

**Impact:**
- `struct_data.properties` contains only: `name`, `type`, `display_name`
- No `guid`, `export_flags`, or `replication` fields
- Property order preserved from source

---

## 19. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-08-17 | Initial design draft |
| 1.1 | 2026-08-17 | Resolved open questions with recommended decisions |
| 1.2 | 2026-08-17 | Added additional types (opaque stubs) to documentation |
| 1.3 | 2026-08-26 | Recorded completion of all nine semantic asset families |

---

*Implemented design for #557 on `dev-0.5.5`.*
