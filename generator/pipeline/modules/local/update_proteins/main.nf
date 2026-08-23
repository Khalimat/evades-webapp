process UPDATE_PROTEINS {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta), path(metadata) 
    path db

    output:
    tuple val(meta), path("${db}")

    script:
    """
    update_proteins.py \\
        --input_json ${metadata}
    """
}
