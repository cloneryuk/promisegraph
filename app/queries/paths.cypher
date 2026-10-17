MATCH p=(c:Entity {id:$id})-[:REQUIRES*1..8]->(w:Entity)
RETURN [n IN nodes(p) | n.id] AS node_ids,
       [r IN relationships(p) | r.fact_id] AS fact_ids
LIMIT 201

