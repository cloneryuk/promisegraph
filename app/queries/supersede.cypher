MATCH (f:Fact {id:$id}), (old:Fact {id:$old_id}), (s:Slot {id:$slot})
WHERE f.status = 'pending' AND old.status = 'accepted'
  AND size(f.validation_flags) = 0
  AND s.current = old.id AND f.slot_id = s.id AND old.slot_id = s.id
  AND f.kind = old.kind AND f.subject_id = old.subject_id
  AND f.kind IN ['deadline','forecast'] AND f.old_date = old.date
SET f.status = 'accepted', f.reviewed_at = $now, f.review_reason = $reason,
    old.status = 'superseded', old.reviewed_at = $now, s.current = f.id
MERGE (f)-[:SUPERSEDES]->(old)
RETURN f.id

