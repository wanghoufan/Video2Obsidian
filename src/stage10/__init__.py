"""Stage10: Archive Level A/B/C + Source current_path update (§69).

S10-T01 verify_archive (Archive 前 Strong Verify + G3 预门) ->
S10-T02 level_a (Atomic No-Cover) -> S10-T03 level_b (Reservation
Copy + Mid-copy Recovery) -> S10-T04 level_c (Unsupported Block) +
gate (Capability 分流 + G3 装配) + commit (archive_commits 行 +
sources 四列更新).

src/stage1-9 只读复用、零修改. 中央库唯一允许新增行的表为
archive_commits; sources 只许 current_path /
current_location_type / status / archived_at 四列更新.
"""

from stage10.commit import (
    LOCATION_ARCHIVE,
    STATUS_ARCHIVED,
    commit_archive_success,
    resolve_current_path,
)
from stage10.gate import archive_source, probe_archive_capability
from stage10.level_a import archive_level_a
from stage10.level_b import archive_level_b, recover_midcopy
from stage10.level_c import archive_level_c, verdict_unsupported
from stage10.verify_archive import (
    assert_publish_present,
    find_published_for_source,
    read_source_row,
    verify_source_for_archive,
)

__all__ = [
    "LOCATION_ARCHIVE",
    "STATUS_ARCHIVED",
    "archive_level_a",
    "archive_level_b",
    "archive_level_c",
    "archive_source",
    "assert_publish_present",
    "commit_archive_success",
    "find_published_for_source",
    "probe_archive_capability",
    "read_source_row",
    "recover_midcopy",
    "resolve_current_path",
    "verdict_unsupported",
    "verify_source_for_archive",
]
