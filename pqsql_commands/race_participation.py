import os
import pandas as pd
import psycopg2

# PostgreSQL connection details
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME_EXT"),
    user=os.getenv("DB_USER_EXT"),
    password=os.getenv("DB_PASSWORD_EXT"),
    host=os.getenv("DB_HOST_EXT"),
    port=os.getenv("DB_PORT_EXT"),
)

# Query
query = """
    SELECT 
        r.first_name, 
        r.last_name, 
        COUNT(DISTINCT rr.race_id) AS races_participated, 
        STRING_AGG(rr.race_id::TEXT, ', ' ORDER BY rr.race_id ASC) AS race_ids,
        cc.general_points
    FROM 
        classifications_classificationresult cc
    JOIN 
        races_runner r ON cc.runner_id = r.id
    JOIN 
        classifications_classification c ON cc.classification_id = c.id
    JOIN 
        races_result rr ON rr.runner_id = r.id
    WHERE 
        c.slug LIKE 'bellahouston-park-2024-classification'
    GROUP BY 
        r.id, cc.general_points
    ORDER BY 
        cc.general_points ASC;
"""

# Execute query and load into a DataFrame
df = pd.read_sql_query(query, conn)

# Export to Excel
output_file = "pqsql_commands/files/race_participation.xlsx"
df.to_excel(output_file, index=False)

print(f"Data exported to {output_file}")
