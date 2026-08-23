process PARSE_S4PRED_TO_FEATURE_VIEWER {
    tag "$meta.id"
    label 'process_single'

    input:
    tuple val(meta), path(preds) 

    output:
    tuple val(meta), path("output_${preds}")

    script:
    """
    parse_s4pred_to_feature_viewer.py \\
        ${preds} \\
        output_${preds}
    """
}
