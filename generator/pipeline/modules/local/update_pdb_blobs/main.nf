process UPDATE_PDB_BLOBS {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta), path(db) 
    path (structures)

    output:
    tuple val(meta), path("${db}")

    script:
    """
    update_pdb_blobs.py \\
        --db ${db} \\
        --structures ${structures}
    """
}
