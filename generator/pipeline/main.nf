include { EXTRACT_FASTA                    } from './modules/local/extract_fasta/main'
include { S4PRED_RUNMODEL                  } from './modules/nf-core/s4pred/runmodel/main'
include { UPDATE_PROTEINS                  } from './modules/local/update_proteins/main'
include { UPDATE_PDB_BLOBS                 } from './modules/local/update_pdb_blobs/main'
include { UPDATE_EUK_VIRUS_HOMOLOG_BLOBS   } from './modules/local/update_euk_virus_homolog_blobs/main'
include { PARSE_S4PRED_TO_FEATURE_VIEWER   } from './modules/local/parse_s4pred_to_feature_viewer/main'
include { UPDATE_SECONDARY_STRUCTURE_BLOBS } from './modules/local/update_secondary_structure_blobs/main'
include { HMMER_HMMSEARCH                  } from './modules/nf-core/hmmer/hmmsearch/main'
include { PARSE_DOMTBL                     } from './modules/local/parse_domtbl/main'
include { UPDATE_PROTEIN_PFAMS             } from './modules/local/update_protein_pfams/main'

workflow {

    ch_metadata   = Channel.of([ [ id:'anti-defence' ], file(params.input_metadata, checkIfExists: true) ])
    ch_db         = Channel.fromPath(params.db)
    ch_structures = Channel.fromPath(params.structures)
    ch_homologs   = Channel.fromPath(params.homologs)

    EXTRACT_FASTA( ch_metadata )

    S4PRED_RUNMODEL( EXTRACT_FASTA.out )

    UPDATE_PROTEINS( ch_metadata, ch_db )
    UPDATE_PDB_BLOBS( UPDATE_PROTEINS.out, ch_structures )
    UPDATE_EUK_VIRUS_HOMOLOG_BLOBS( UPDATE_PDB_BLOBS.out, ch_homologs )

    PARSE_S4PRED_TO_FEATURE_VIEWER ( S4PRED_RUNMODEL.out.preds )
    UPDATE_SECONDARY_STRUCTURE_BLOBS( PARSE_S4PRED_TO_FEATURE_VIEWER.out, UPDATE_EUK_VIRUS_HOMOLOG_BLOBS.out )
    
    ch_input_for_hmmsearch = EXTRACT_FASTA.out
        .map { meta, seqs -> [ meta, params.pfam_hmm, seqs, false, false, true ] }
    HMMER_HMMSEARCH( ch_input_for_hmmsearch )

    PARSE_DOMTBL( HMMER_HMMSEARCH.out.domain_summary )

    UPDATE_PROTEIN_PFAMS( PARSE_DOMTBL.out, UPDATE_SECONDARY_STRUCTURE_BLOBS.out )

}
