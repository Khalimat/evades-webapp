#!/usr/bin/env python3

import json
import os
import sys
import argparse
import django

# Add the path to the Django project
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../website/anti_defence")))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'anti_defence.settings')
django.setup()

from explorer.models import Protein, ProteinDefences

def handle_empty(value):
    """Convert "_" or empty string to None."""
    return None if value in ('_', '') else value

def update_proteins(input_json):
    with open(input_json, "r") as f:
        data = json.load(f)

    for record in data:
        protein, created = Protein.objects.update_or_create(
            id=record["ID"],
            defaults={
                "name": handle_empty(record.get("Name")),
                "moa": handle_empty(record.get("MoA")),
                "evidence": handle_empty(record.get("Evidence")),
                "moa_category": handle_empty(record.get("MoA category")),
                "defence_subtype": handle_empty(record.get("Defence subtype")),
                "sequence": handle_empty(record.get("Protein sequence")),
                "doi": handle_empty(record.get("DOI")),
                "multicomponent": handle_empty(record.get("Multicomponent system")),
                "pdb": handle_empty(record.get("PDB")),
                "pdb_filename": handle_empty(record.get("Structure")),
                "pdb_blob": None,  # Leaving out structure loading for now
                "structure_type": handle_empty(record.get("Type of the 3D structure")),
                "existing_pfams": handle_empty(record.get("Existing Pfam domain")),
                "euk_virus_homologs_filename": handle_empty(record.get("Homologs from eukaryotic viruses")),
                "euk_virus_homologs_blob": None,
                "protein_source_name": handle_empty(record.get("Protein source", {}).get("name")),
                "protein_source_link": handle_empty(record.get("Protein source", {}).get("link")),
                "pred_secondary_structure_file": None,
                "pred_secondary_structure_blob": None
            }
        )

        # Clear and re-add defences if any
        ProteinDefences.objects.filter(protein=protein).delete()
        for defence in record.get("defences", []):
            ProteinDefences.objects.create(
                protein=protein,
                defence_name=handle_empty(defence.get("defence_name")),
                defence_link=handle_empty(defence.get("link"))
            )

        print(f"{'Created' if created else 'Updated'} Protein: {protein.id}")

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Load protein data from JSON into Django models.")
    parser.add_argument("--input_json", required=True, help="Path to input JSON file")
    args = parser.parse_args()
    # # Test connection
    # try:
    #     protein_count = Protein.objects.count()
    #     print(f"Database connection successful! Protein table has {protein_count} entries.")
    # except Exception as e:
    #     print(f"Database connection failed: {e}")

    # Update proteins using the metadata file
    update_proteins(args.input_json)
