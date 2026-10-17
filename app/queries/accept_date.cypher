MATCH (f:Fact {id:$id}), (s:Slot {id:$slot})
WHERE f.status = 'pending' AND size(f.validation_flags) = 0
  AND s.current = '' AND f.slot_id = s.id
  AND f.kind IN ['deadline','forecast']
SET f.status = 'accepted', f.reviewed_at = $now, f.review_reason = $reason, s.current = f.id
RETURN f.id

