process UPDATE_PROTEIN_PFAMS {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta) , path(domtbl) 
    tuple val(meta2), path(db) 

    output:
    tuple val(meta2), path("${db}")

    script:
    """
    update_protein_pfams.py \\
        --domtbl_csv ${domtbl} \\
        --db ${db}
    """
}
