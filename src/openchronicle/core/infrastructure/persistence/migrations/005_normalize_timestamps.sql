-- Normalize timestamp text to UTC without losing microseconds.
-- The Python migration runner registers oc_normalize_utc after rejecting
-- ambiguous or malformed legacy rows, inside the migration savepoint.

UPDATE projects
SET created_at = oc_normalize_utc(created_at)
WHERE created_at != oc_normalize_utc(created_at);

UPDATE memory_items
SET created_at = oc_normalize_utc(created_at),
    updated_at = oc_normalize_utc(updated_at)
WHERE created_at != oc_normalize_utc(created_at)
   OR (updated_at IS NOT NULL AND updated_at != oc_normalize_utc(updated_at));
