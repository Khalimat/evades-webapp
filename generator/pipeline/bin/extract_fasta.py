#!/usr/bin/env python3

import argparse
import json

def extract_fasta(input_file, output_fasta):
    # Load the JSON data
    with open(input_file, "r") as json_file:
        data = json.load(json_file)

    # Open the output FASTA file
    with open(output_fasta, "w") as fasta_file:
        for record in data:
            name = record["ID"]
            sequence = record["Protein sequence"].replace(" ", "") # Removing in-sequence spaces that are not supposed to be there
            fasta_file.write(f">{name}\n{sequence}\n")

    print(f"FASTA file '{output_fasta}' has been created successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract protein sequences from a JSON file into FASTA format.")
    parser.add_argument("--input_file", required=True, help="Path to the input metadata JSON file.")
    parser.add_argument("--output_fasta", required=True, help="Path to the output FASTA file.")

    args = parser.parse_args()

    extract_fasta(args.input_file, args.output_fasta)
