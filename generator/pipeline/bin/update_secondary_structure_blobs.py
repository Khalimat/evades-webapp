#!/usr/bin/env python3

import os
import argparse
import sqlite3

def update_protein_table(folder_path, db_path):
    """
    Updates the `protein` table with file names and blobs for JSON predictions.
    
    Args:
        folder_path (str): Path to the folder containing JSON files.
        db_path (str): Path to the SQLite database.
    """
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Disable synchronous for faster writes (use with caution)
    cursor.execute("PRAGMA synchronous = OFF")
    # Begin a transaction
    cursor.execute("BEGIN TRANSACTION")

    # Iterate over all files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            
            # Extract the ID from the filename (basename without extension)
            protein_id = os.path.splitext(filename)[0]
            print(f"Processing {protein_id}")

            # Define your query with placeholders
            query = """
            SELECT pred_secondary_structure_file, pred_secondary_structure_blob
            FROM protein
            WHERE UPPER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(id, '.', '_'), '/', '_'), '*', '_'), ' ', '_'), '-', '')) = ?
            """

            # Define the parameter
            parameter = protein_id

            # DEBUG: Print the query with the parameter
            # print(query.replace("?", f"'{parameter}'"))

            # Execute the query
            cursor.execute(query, (parameter,))

            result = cursor.fetchone()
            
            if result and result[0] is not None and result[1] is not None:
                # Skip if already updated
                print(f"Skipping {protein_id}, already updated.")
                continue

            # Read the JSON file as a blob
            with open(file_path, 'rb') as file:
                file_blob = file.read()

            # Update the database for the matching ID
            cursor.execute(
                """
                UPDATE protein
                SET pred_secondary_structure_file = ?,
                    pred_secondary_structure_blob = ?
                WHERE UPPER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(id, '.', '_'), '/', '_'), '*', '_'), ' ', '_'), '-', '')) = ?
                """,
                (filename, file_blob, protein_id)
            )

    # Commit changes and close the connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Update protein table with JSON predictions.")
    parser.add_argument("folder_path", type=str, help="Path to the folder containing JSON files.")
    parser.add_argument("db_path", type=str, help="Path to the SQLite database.")

    args = parser.parse_args()
    # Example: ./bin/update_secondary_structure_blobs.py /home/vangelis/Desktop/Projects/mgnifams-post-pipeline-scripts/output/s4pred/anti_defence /home/vangelis/Desktop/Projects/anti_defence/anti_defence/dbs/anti_defence.sqlite3

    # Run the update function
    update_protein_table(args.folder_path, args.db_path)
