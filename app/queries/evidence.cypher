MATCH (f:Fact)-[:SUPPORTED_BY]->(s:Span)<-[:HAS_SPAN]-(d:Document)
WHERE f.id IN $ids
OPTIONAL MATCH (p:Person)-[:AUTHORED]->(d)
RETURN properties(f), properties(s), properties(d), properties(p)

