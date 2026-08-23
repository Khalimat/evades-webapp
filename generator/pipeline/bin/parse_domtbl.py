#!/usr/bin/env python3

import argparse
import gzip

def parse_hmmsearch(input_file, output_file):
    with (
        gzip.open(input_file, "rt")
        if input_file.endswith(".gz")
        else open(input_file, "r")
    ) as infile, open(output_file, 'w') as outfile:
        # Write the header with specified columns
        outfile.write("protein_name,protein_length,pfam_name,pfam_accession,pfam_length,e-value,hmm_from,hmm_to,ali_from,ali_to,env_from,env_to\n")

        for line in infile:
            # Skip comment lines (lines that start with '#')
            if line.startswith('#'):
                continue

            # Split the line by whitespace into columns
            columns = line.strip().split()
            
            # Extract necessary columns
            target_name = columns[0]  # Target name
            tlen = columns[2]  # tlen
            query_name = columns[3]  # Query name
            query_accession = columns[4]  # Query accession
            qlen = columns[5]  # qlen
            e_value = columns[6]  # E-value
            hmm_from = columns[15]  # hmm_from
            hmm_to = columns[16]  # hmm_to
            ali_from = columns[17]  # ali_from
            ali_to = columns[18]  # ali_to
            env_from = columns[19]  # env_from
            env_to = columns[20]  # env_to
            description_of_target = " ".join(columns[22:])  # Description of target

            # Concatenate description to target name if it's not "-"
            if description_of_target != "-":
                target_name = f"{target_name} {description_of_target}"

            # Write the row to the output file
            outfile.write(f"{target_name},{tlen},{query_name},{query_accession},{qlen},{e_value},{hmm_from},{hmm_to},{ali_from},{ali_to},{env_from},{env_to}\n")

    print(f"Parsing complete. Results saved to {output_file}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse hmmsearch results.")
    parser.add_argument("--domtbl", required=True, help="Path to the domtblout result.")
    parser.add_argument("--out_csv", required=True, help="Path to the parsed output CSV file.")

    args = parser.parse_args()

    parse_hmmsearch(args.domtbl, args.out_csv)

# # Usage
# input_file = "./assets/annotated_results_fa_1_anti-defence.domtbl"
# output_file = "./assets/protein_pfams.csv" 
# parse_hmmsearch(input_file, output_file)
