# Design: MovieScene StructProperty Parsing (Issue #515)

## Problem Statement

Several MovieScene-related struct types are currently parsed as `opaque` with empty `fields`. The most common are:
- MovieSceneDoubleChannel: 27 occurrences
- MovieSceneFrameRange: 13 occurrences
- MovieSceneFloatChannel: 11 occurrences

These are Sequencer-related structures used for animation curves and keyframes.

## Selected Struct: MovieSceneDoubleChannel

### Rationale
- Highest frequency (27 occurrences)
- Available in `Lyra_SEQ_LobbyScreen_LevelSequence.uasset`
- Relatively simple structure (animation keyframe channel)

### UE Source Reference

Based on UE source (Engine/Source/Runtime/MovieScene/Public/MovieSceneChannel.h):

```cpp
struct FMovieSceneDoubleChannel
{
    FMovieSceneChannelTraits Traits;
    TArray<FMovieSceneDoubleValue> Values;
    TArray<FFrameNumber> Times;
    FFrameRate TickResolution;
    bool bHasDefaults;
    FMovieSceneDoubleValue DefaultValue;
    FFrameNumber TickResolutionFrameNumber;
};
```

### Binary Layout (Little-Endian)

1. **Traits** (optional, version-gated): Channel metadata
2. **Values count** (i32): Number of keyframe values
3. **Values** (repeated):
   - Value (f64): Double precision keyframe value
   - Interpolation (u8): Interpolation type
4. **Times count** (i32): Number of keyframe times
5. **Times** (repeated):
   - FrameNumber (i32): Frame number
6. **TickResolution** (optional): Frame rate information
7. **bHasDefaults** (u8): Whether default value exists
8. **DefaultValue** (optional): Default value if bHasDefaults

### Acceptance Criteria

- [ ] Parse MovieSceneDoubleChannel from real fixture
- [ ] Extract keyframe times and values
- [ ] Preserve raw fallback for malformed data
- [ ] Add unit tests for edge cases
- [ ] Verify with Lyra_SEQ_LobbyScreen_LevelSequence.uasset

## Implementation Plan

### Phase 1: Design and Red Test

1. Create design document (this file)
2. Write failing test that expects parsed fields
3. Verify test fails with current implementation

### Phase 2: Implement Parser

1. Add MovieSceneDoubleChannel parser to property_types.py
2. Handle version differences (UE4 vs UE5)
3. Preserve raw fallback for malformed data

### Phase 3: Verify and Document

1. Run tests against real fixture
2. Document binary format in docs/formats/
3. Commit with evidence

## Non-Goals

- Implement all MovieScene struct types (future work)
- Handle editor-only metadata
- Reconstruct visual timeline layout
