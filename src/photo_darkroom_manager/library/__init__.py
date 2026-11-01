"""Library domain: darkroom layout, media kinds, tree model and scanning.

Models and functions only; the engine holds the scanned tree.
"""

from photo_darkroom_manager.library._scan import scan_subtree
from photo_darkroom_manager.library.layout import (
    BATCH_PATTERN,
    PHOTOS_FOLDER,
    PUBLISH_FOLDER,
    VIDEOS_FOLDER,
    BatchFolderName,
    DarkroomBatch,
    NodeKind,
    child_kind,
    format_validation_error,
    recognize_darkroom_batch,
    validate_device_name,
)
from photo_darkroom_manager.library.media import (
    ALL_IMAGE_EXTENSIONS,
    PHOTO_EXTENSIONS,
    RAW_IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    collect_files_to_tidy,
    is_file_a_photo,
    is_file_a_video,
    is_untidy,
)
from photo_darkroom_manager.library.tree import (
    FileCounts,
    LibraryTree,
    NodeAction,
    NodeFacts,
    NodeId,
    NodeIssue,
    NodeView,
    child_id,
    node_actions,
    parent_id,
)

__all__ = [
    "ALL_IMAGE_EXTENSIONS",
    "BATCH_PATTERN",
    "PHOTOS_FOLDER",
    "PHOTO_EXTENSIONS",
    "PUBLISH_FOLDER",
    "RAW_IMAGE_EXTENSIONS",
    "VIDEOS_FOLDER",
    "VIDEO_EXTENSIONS",
    "BatchFolderName",
    "DarkroomBatch",
    "FileCounts",
    "LibraryTree",
    "NodeAction",
    "NodeFacts",
    "NodeId",
    "NodeIssue",
    "NodeKind",
    "NodeView",
    "child_id",
    "child_kind",
    "collect_files_to_tidy",
    "format_validation_error",
    "is_file_a_photo",
    "is_file_a_video",
    "is_untidy",
    "node_actions",
    "parent_id",
    "recognize_darkroom_batch",
    "scan_subtree",
    "validate_device_name",
]
