#!/usr/bin/env python3

import os
import sqlite3
import argparse

def update_euk_virus_homolog_blobs(db_path, homologs_folder):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Retrieve all rows from the Protein table
    cursor.execute("SELECT id, euk_virus_homologs_filename FROM Protein")
    rows = cursor.fetchall()

    # Iterate over each row
    for row in rows:
        protein_id, euk_virus_homologs_filename = row

        if euk_virus_homologs_filename:
            # Construct the full path to the .html file. The metadata
            # references "<id>_model.html" but the homolog folder as
            # produced upstream just has "<id>.html" — normalize.
            actual_filename = euk_virus_homologs_filename.replace("_model.html", ".html")
            homolog_file_path = os.path.join(homologs_folder, actual_filename)

            # Check if the .pdb file exists
            if os.path.exists(homolog_file_path):
                # Read the contents of the .pdb file
                with open(homolog_file_path, 'rb') as file:
                    euk_virus_homologs_blob = file.read()

                # Update the euk_virus_homologs_blob column
                cursor.execute("UPDATE Protein SET euk_virus_homologs_blob = ? WHERE id = ?", (euk_virus_homologs_blob, protein_id))
            else:
                print(f"Warning: .html file not found for protein {protein_id}: {euk_virus_homologs_filename}")

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update the euk_virus_homologs_blob column in the Protein table.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--homologs", required=True, help="Path to the folder containing the HTML pages with euk virus homologs.")

    args = parser.parse_args()

    update_euk_virus_homolog_blobs(args.db, args.homologs)
