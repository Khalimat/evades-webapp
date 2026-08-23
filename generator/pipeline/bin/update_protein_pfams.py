#!/usr/bin/env python3

import csv
import os
import sys
import argparse
import django

# Add the path to the Django project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../website/anti_defence")))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anti_defence.settings')
django.setup()

from explorer.models import ProteinPfams

def handle_empty(value):
    """Convert "_" or empty string to None."""
    return None if value in ('_', '') else value

def update_protein_pfams(domtbl_csv):
    """Reads a TSV file and updates the ProteinPfams model."""
    with open(domtbl_csv, 'r') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            protein_id = handle_empty(row['protein_name'])
            print(protein_id)
            
            if not protein_id:
                continue  # Skip rows without an ID

            # Extract values
            pfam_name = handle_empty(row['pfam_name'])
            pfam_accession = handle_empty(row['pfam_accession'])
            pfam_length = int(row['pfam_length'])
            e_value = float(row['e-value'])
            hmm_from = int(row['hmm_from'])
            hmm_to = int(row['hmm_to'])
            ali_from = int(row['ali_from'])
            ali_to = int(row['ali_to'])
            env_from = int(row['env_from'])
            env_to = int(row['env_to'])

            # Check if an exact match exists
            exists = ProteinPfams.objects.filter(
                protein_id=protein_id,
                pfam_name=pfam_name,
                pfam_accession=pfam_accession,
                pfam_length=pfam_length,
                e_value=e_value,
                hmm_from=hmm_from,
                hmm_to=hmm_to,
                ali_from=ali_from,
                ali_to=ali_to,
                env_from=env_from,
                env_to=env_to,
            ).exists()

            if not exists:
                # Create a new entry only if no exact match exists
                ProteinPfams.objects.create(
                    protein_id=protein_id,
                    pfam_name=pfam_name,
                    pfam_accession=pfam_accession,
                    pfam_length=pfam_length,
                    e_value=e_value,
                    hmm_from=hmm_from,
                    hmm_to=hmm_to,
                    ali_from=ali_from,
                    ali_to=ali_to,
                    env_from=env_from,
                    env_to=env_to,
                )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update the ProteinPfams table from a TSV file.")
    parser.add_argument("--domtbl_csv", required=True, help="Path to the metadata TSV file.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")

    args = parser.parse_args()
    
    # Update ProteinPfams using the metadata file
    update_protein_pfams(args.domtbl_csv)
