process S4PRED {
    tag "$meta.id"
    label 'process_high'

    conda "${moduleDir}/environment.yml"

    input:
    tuple val(meta), path(fasta)

    output:
    tuple val(meta), path("preds"), emit: preds
    path "versions.yml"           , emit: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def VERSION='1.2.0'
    prefix = task.ext.prefix ?: "${meta.id}"
    """
    run_model.py \\
        --outfmt horiz \\
        --save-files \\
        ${fasta}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        s4pred: ${VERSION}
    END_VERSIONS
    """

    stub:
    def VERSION='1.2.0'
    prefix = task.ext.prefix ?: "${meta.id}"
    """
    mkdir preds
    touch preds/empty.json

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        s4pred: ${VERSION}
    END_VERSIONS
    """
}
