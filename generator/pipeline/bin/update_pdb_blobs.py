#!/usr/bin/env python3

import os
import sqlite3
import argparse

def update_pdb_blobs(db_path, structures_folder):
    """
    Updates the pdb_blob column in the Protein table with the contents of the corresponding .pdb file.

    Args:
        db_path (str): Path to the SQLite database file.
        structures_folder (str): Path to the folder containing the 3D .pdb structures.
    """
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Retrieve all rows from the Protein table
    cursor.execute("SELECT name, pdb_filename FROM Protein")
    rows = cursor.fetchall()

    # Iterate over each row
    for row in rows:
        protein_id, pdb_filename = row

        # Construct the full path to the .pdb file
        pdb_file_path = os.path.join(structures_folder, pdb_filename.strip())

        # Check if the .pdb file exists
        if os.path.exists(pdb_file_path):
            # Read the contents of the .pdb file
            with open(pdb_file_path, 'rb') as file:
                pdb_blob = file.read()

            # Update the pdb_blob column
            cursor.execute("UPDATE Protein SET pdb_blob = ? WHERE name = ?", (pdb_blob, protein_id))
        else:
            print(f"Warning: .pdb file not found for protein {protein_id}: {pdb_filename}")

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update the pdb_blob column in the Protein table.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--structures", required=True, help="Path to the folder containing the 3D .pdb structures.")

    args = parser.parse_args()

    update_pdb_blobs(args.db, args.structures)
