process PARSE_DOMTBL {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta), path(domtbl) 

    output:
    tuple val(meta), path("protein_pfams.csv")

    script:
    """
    parse_domtbl.py \\
        --domtbl ${domtbl} \\
        --out_csv protein_pfams.csv
    """
}
