process EXTRACT_FASTA {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta), path(metadata) 

    output:
    tuple val(meta), path("proteins.fasta")

    script:
    """
    extract_fasta.py \\
        --input_file ${metadata} \\
        --output_fasta proteins.fasta
    """
}
