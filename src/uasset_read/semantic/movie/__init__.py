"""Movie semantic JSON domain (#557i)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.movie.extractor import build_movie_content
from uasset_read.semantic.validator import register_domain_validator, validate_movie_document

for _class in ("MovieScene", "LevelSequence",
               "MovieSceneControlRigParameterTrack", "MovieSceneControlRigParameterSection"):
    register_extension(
        _class,
        build_movie_content,
        domain_format="uasset_read.movie_semantic",
        domain_format_version="1.0.0",
    )
register_domain_validator("uasset_read.movie_semantic", validate_movie_document)
