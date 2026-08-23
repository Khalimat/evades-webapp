process UPDATE_SECONDARY_STRUCTURE_BLOBS {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta) , path(json) 
    tuple val(meta2), path(db)

    output:
    tuple val(meta2), path("${db}")

    script:
    """
    update_secondary_structure_blobs.py \\
        ${json} \\
        ${db}
    """
}