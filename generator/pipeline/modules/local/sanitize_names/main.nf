process SANITIZE_NAMES {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta), path(fasta) 

    output:
    tuple val(meta), path("cleaned_${fasta}")

    script:
    """
    sanitise_names.py \\
        --input_fasta ${fasta} \\
        --output_fasta cleaned_${fasta}
    """
}
