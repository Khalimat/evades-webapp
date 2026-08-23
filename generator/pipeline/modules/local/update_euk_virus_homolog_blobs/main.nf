process UPDATE_EUK_VIRUS_HOMOLOG_BLOBS {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta), path(db) 
    path (homologs)

    output:
    tuple val(meta), path("${db}")

    script:
    """
    update_euk_virus_homolog_blobs.py \\
        --db ${db} \\
        --homologs ${homologs}
    """
}
