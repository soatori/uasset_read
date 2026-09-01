"""Payloads — extraction markers for large binary data.

Payloads are references to bulk data (textures, audio, meshes) stored
in external regions (.uexp, .ubulk, .uptnl, .ucas). Extraction is
deferred until container-backed source regions and legitimate sample
fixtures exist (issue #621); ``agent_tools.extract_payload`` reports
this via the constants below.
"""

PAYLOAD_EXTRACTION_DEFERRED = "PAYLOAD_EXTRACTION_DEFERRED"

PAYLOAD_EXTRACTION_DEFERRED_MESSAGE = (
    "Payload extraction is deferred: real payloads require "
    ".uexp/.ubulk/.utoc/.ucas container support (issue #621)"
)
