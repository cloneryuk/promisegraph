MATCH (new:Fact)-[:SUPERSEDES]->(old:Fact)
RETURN properties(new), properties(old)
