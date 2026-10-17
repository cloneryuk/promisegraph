MATCH (f:Fact {id:$id}), (a:Entity {id:$subject}), (b:Entity {id:$object})
WHERE f.status = 'pending' AND size(f.validation_flags) = 0
  AND f.kind = 'requires' AND f.subject_id = a.id AND f.object_id = b.id
  AND b.kind = 'work' AND NOT (a)-[:REQUIRES]->(b)
SET f.status = 'accepted', f.reviewed_at = $now, f.review_reason = $reason
MERGE (a)-[:REQUIRES {fact_id:f.id}]->(b)
RETURN f.id

