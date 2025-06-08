import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('test_08_db.db')

# Create a cursor object
cursor = conn.cursor()

# Execute a query to fetch all rows from the 'users' table
cursor.execute("SELECT * FROM schedules")

# Fetch all rows from the executed query
rows = cursor.fetchall()

# Print the contents of the 'users' table
for row in rows:
    print(row)

# Close the connection
conn.close()

print(rows)